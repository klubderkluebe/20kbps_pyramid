import dateutil.parser as dateparser
import glob
import itertools
import os.path
import re
import threading
import time
import typing as t
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum

from pyramid.threadlocal import get_current_registry

import mutagen
import requests
import zipfile
from pathvalidate import validate_filename

from . import models
from .storage_client import get_storage_client

import logging


log = logging.getLogger(__name__)
settings = get_current_registry().settings


MUSIC_EXTENSIONS = ("mp3", "ogg", "opus",)
IMAGE_EXTENSIONS = ("jpg", "png",)
ARTIST_TAG = "TPE1"
ALBUM_TAG = "TALB"
TITLE_TAG = "TIT2"
VARIOUS_ARTISTS_NAME = "VA"

SANITIZE_ALPHABET = ".-_0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
SANITIZE_MAXLEN = 255

ptn_catno = re.compile(r"\((20k.*?)\)")
ptn_tag = re.compile(r"[\dA-Z]{4}")


def sanitize(s):
    t = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()
    t = t.replace(" ", "_")
    t = "".join(ch for ch in t if ch in SANITIZE_ALPHABET)
    if len(t) > SANITIZE_MAXLEN:
        stem, dotext = os.path.splitext(t)
        max_stem_len = SANITIZE_MAXLEN - len(dotext)
        cropped_stem = stem[:max_stem_len]
        t = f"{cropped_stem}{dotext}"
    return t


class RequestType(IntEnum):
    PREVIEW = 0
    UPLOAD = 1


@dataclass
class QueuedRequest:
    request_type: RequestType
    file: t.Optional[str] = None
    data: t.Optional[dict] = None


@dataclass
class TaskState:
    success: t.Optional[bool] = None  # None = pending
    data: dict = field(default_factory=dict)
    exception: t.Optional[Exception] = None

    def serialize(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "exception":self.exception,
        }


class ReleaseCreator:
    def __init__(self):
        self.queue: deque[QueuedRequest] = deque()
        self.task_state: t.Dict[t.Tuple[RequestType, str], TaskState] = {}
        self.thread = threading.Thread(target=self.thread_fn)
        self.thread.start()

    def thread_fn(self):
        if not getattr(self, "last", None):
            self.last = time.time()
        while True:            
            time.sleep(0)
            if len(self.queue):
                req = self.queue.popleft()
                data = t.cast(dict, req.data)
                match req.request_type:
                    case RequestType.PREVIEW:
                        file = t.cast(str, req.file)
                        self.task_state[RequestType.PREVIEW, file] = TaskState()
                        local_dir = self.process_zip_file(file)
                        if local_dir:
                            self.process_local_dir(file, local_dir)
                    case RequestType.UPLOAD:
                        file: str = data["file"]
                        self.task_state[RequestType.UPLOAD, file] = TaskState(data=data)
                        self.upload_player_files(file)

    def request_preview(self, file: str):
        self.queue.append(QueuedRequest(RequestType.PREVIEW, file))

    def request_upload(self, file: str):
        preview_key = (RequestType.PREVIEW, file)
        preview_state = self.task_state[preview_key]
        self.queue.append(QueuedRequest(RequestType.UPLOAD, data=preview_state.data))

    def process_zip_file(self, file):
        tmpdir = settings["tmp_directory"]
        local_dir = os.path.join(tmpdir, file.replace(".zip", ""))

        try:
            res = requests.get(
                f"{settings['static_base']}/Releases/{file}"
            )
            log.info(f"ReleaseCreator.zip_downloaded | file='{file}'")
            local_file = os.path.join(tmpdir, file)
            with open(local_file, "wb") as f:
                f.write(res.content)
            with zipfile.ZipFile(local_file, "r") as f:
                f.extractall(local_dir)
            log.info(f"ReleaseCreator.zip_extracted | file='{file}' | local_dir='{local_dir}'")
        except Exception as ex:
            self.task_state[RequestType.PREVIEW, file].success = False
            self.task_state[RequestType.PREVIEW, file].exception = ex
            return None
        
        return local_dir

    def process_local_dir(self, file, local_dir):
        data = self.task_state[RequestType.PREVIEW, file].data = {
            "local_dir": local_dir,
            "catalog_no": ptn_catno.search(local_dir).groups()[0],  # type: ignore
            "file": file,
        }

        try:
            music_files = sorted(list(itertools.chain.from_iterable(
                glob.glob(f"{local_dir}/*.{ext}")
                for ext in MUSIC_EXTENSIONS
            )))

            assert glob.glob(f"{local_dir}/cover.jpg"), "Missing cover.jpg"

            player_files = []
            albums = set()
            for i, f in enumerate(music_files, 1):
                mf = mutagen.File(f)  # type: ignore
                tags = mf.tags  # type: ignore
                music_file = sanitize(os.path.basename(f))
                try:
                    validate_filename(music_file)
                except:
                    # File name is too garbled. Just use number.
                    _, dotext = os.path.splitext(music_file)
                    music_file = f"{i:02}{dotext}"
                player_files.append({
                    "_artist": str(tags[ARTIST_TAG]),
                    "file": music_file,
                    "number": i,
                    "title": str(tags[TITLE_TAG]),
                    "duration_secs": round(mf.info.length),  # type: ignore
                })
                albums.add(str(tags[ALBUM_TAG]))

            assert len(albums) == 1, f"More than one album given in {ALBUM_TAG} tag"
            album = albums.pop()

            artists = {pf["_artist"] for pf in player_files}
            if len(artists) == 1:
                artist = artists.pop()
            else:
                artist = VARIOUS_ARTISTS_NAME
                for pf in player_files:
                    pf["title"] = f"{pf['_artist']} - {pf['title']}"
            for pf in player_files:
                del pf["_artist"]

            data.update({
                "local_files": music_files,
                "release_dir": os.path.join(sanitize(artist.lower()), sanitize(album.lower())),
                "release_data": {
                    "relname": album,
                    "artist": artist,
                    "cat-no": data["catalog_no"],
                    "description": f"{artist} - {album} ({data['catalog_no']})",
                    "list": "ol",
                    "date": datetime.now().isoformat()[:10],
                },
                "player_files": player_files,
            })
        except Exception as ex:
            self.task_state[RequestType.PREVIEW, file].success = False
            self.task_state[RequestType.PREVIEW, file].exception = ex
            return None

        self.task_state[RequestType.PREVIEW, file].success = True
        return data

    def upload_player_files(self, file):
        data = self.task_state[RequestType.UPLOAD, file].data

        log.info(f"upload_player_files | data={data}")

        try:
            storage = get_storage_client()
            remote_rlsdir = os.path.join("Releases", data["release_dir"])
            for local, pf in zip(data["local_files"], data["player_files"]):
                remote = os.path.join(remote_rlsdir, pf["file"])
                log.info(f"ReleaseCreator.upload_player_file | local='{local}' | remote='{remote}'")
                storage.upload(local, remote)
                time.sleep(0)                
            storage.upload(
                os.path.join(data["local_dir"], "cover.jpg"),
                os.path.join(remote_rlsdir, "cover.jpg")
            )
        except Exception as ex:
            self.task_state[RequestType.UPLOAD, file].success = False
            self.task_state[RequestType.UPLOAD, file].exception = ex
        
        self.task_state[RequestType.UPLOAD, file].success = True

    def create_database_objects(self, file, dbsession, page_content, index_record_body):
        data = self.task_state[RequestType.UPLOAD, file].data

        release = models.Release(
            catalog_no=data["catalog_no"],
            release_dir=data["release_dir"],
            file=data["file"],
            release_data=data["release_data"],
        )
        dbsession.add(release)
        dbsession.flush()

        rp = models.ReleasePage(
            release=release,
            content=page_content,
        )
        dbsession.add(rp)
        dbsession.flush()

        for pf in data["player_files"]:
            pf = models.PlayerFile(
                release_page=rp,
                file=pf["file"],
                number=pf["number"],
                title=pf["title"],
                duration_secs=pf["duration_secs"],
            )
            dbsession.add(pf)
        dbsession.flush()

        ymd = data["release_data"]["date"]
        date = dateparser.parse(ymd)

        ir = models.IndexRecord(
            date=date.strftime("%d. %b %y"),
            body=index_record_body,
            releases=[release],
        )
        dbsession.add(ir)
        dbsession.flush()


release_creator = ReleaseCreator()
