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

import transaction
from pyramid.threadlocal import get_current_registry
from sqlalchemy import engine_from_config
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.sql.expression import func

import mutagen
import requests
import zipfile
from cachetools import cached
from pathvalidate import validate_filename

from . import models
from .archive_org_client import ArchiveOrgClient
from .storage_client import get_storage_client

import logging


log = logging.getLogger(__name__)
settings = get_current_registry().settings


MUSIC_EXTENSIONS = ("mp3", "ogg", "opus",)
IMAGE_EXTENSIONS = ("jpg", "png",)
ARTIST_TAG = {".mp3": "TPE1", ".ogg": "ARTIST", ".opus": "ARTIST"}
ALBUM_TAG = {".mp3": "TALB", ".ogg": "ALBUM", ".opus": "ALBUM"}
TITLE_TAG = {".mp3": "TIT2", ".ogg": "TITLE", ".opus": "TITLE"}
VARIOUS_ARTISTS_NAME = "VA"

SANITIZE_ALPHABET = ".-_0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
SANITIZE_MAXLEN = 255

ptn_catno = re.compile(r"\((.*?)\)-\d{4}$")


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
    IA_UPLOAD = 2  # Internet Archive upload


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


class ReleaseService:
    """The ReleaseService internally runs a task queue in a worker thread.
    The task queue processes a release along the pipeline, from downloading the release zip file from
    cloud storage to submitting a release to archive.org.
    Admin views enqueue tasks using ReleaseService's `request_*` methods.
    Additional synchronous methods are provided and are invoked by views to finalize a processed release by
    inserting rows for it into the database (`create_database_objects`), and to delete a release
    (`delete_database_objects`).
    """
    def __init__(self):
        self.queue: deque[QueuedRequest] = deque()
        self.task_state: t.Dict[t.Tuple[RequestType, str], TaskState] = {}
        self.thread = threading.Thread(target=self.thread_fn)
        self.thread.start()

    def thread_fn(self):
        """Worker thread function. Pop requests from the queue and process them.
        """
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
                    case RequestType.IA_UPLOAD:
                        file = t.cast(str, req.file)
                        self.task_state[RequestType.IA_UPLOAD, file] = TaskState()
                        local_dir = self.process_zip_file(file, reuse_existing=True)
                        if local_dir:
                            self.upload_to_ia(file, local_dir)

    def request_preview(self, file: str):
        """Request release preview. The admin interface invokes this when a release zip file name is submitted
        as the first step in creating the release.

        The zip file is then downloaded from cloud storage and extracted into a temp directory. The files inside
        the temp directory are processed to generate a preview.

        :param file: Release zip file name. This file is expected to exist inside the `Releases` directory
            in cloud storage.
        """
        self.queue.append(QueuedRequest(RequestType.PREVIEW, file))

    def request_upload(self, file: str):
        """Request upload of the release's individual files to the release directory. The admin interface
        invokes this when proceeding from the preview step.

        The individual files that were extracted into a temp directory for generating the preview are now
        uploaded into the release directory in cloud storage. (The release directory is implicitly created
        if not present.) The release directory is publicly accessible and is the location from where the
        release page is served.

        :param file: Release zip file name
        """
        preview_state = self.task_state[RequestType.PREVIEW, file]
        self.queue.append(QueuedRequest(RequestType.UPLOAD, data=preview_state.data))

    def request_ia_upload(self, file: str):
        """Request submission of a release to archive.org. The admin interface invokes this when the
        `Upload to archive.org` button is clicked on the release edit page.

        :param file: Release zip file name
        """
        self.queue.append(QueuedRequest(RequestType.IA_UPLOAD, file))

    def process_zip_file(self, file, reuse_existing=False):
        """Download release zip file from cloud storage and extract it into temp directory.

        INTERNAL. Invoked by `ReleaseService` itself when processing a `PREVIEW` request.

        :param file: Release zip file name. This file is expected to exist inside the `Releases` directory
            in cloud storage.

        :param reuse_existing: When `True`, and a matching temp directory is found, the existing temp directory
            is reused instead of downloading and extracting the zip file again. This is only set to `True`
            in the archive.org upload step. In the preview phase, the zip file is expected to be re-downloaded
            in order to reflect any changes that are made to it.
        """
        tmpdir = settings["tmp_directory"]
        local_dir = os.path.join(tmpdir, file.replace(".zip", ""))

        if (
            reuse_existing
            and os.path.exists(os.path.join(local_dir, "cover.jpg"))
        ):
            return local_dir

        try:
            res = requests.get(
                f"{settings['static_base']}/Releases/{file}"
            )
            assert res.status_code == 200, f"File download failed (res.status_code={res.status_code})"            
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

    def _get_tag_value(self, tags: t.Mapping[str, t.Any], key: str) -> str:
        v = tags[key]
        if isinstance(v, list):
            return v[0]
        return str(v)

    def _get_artist_tag(self, dotext: str, tags: t.Mapping[str, t.Any]) -> str:
        return self._get_tag_value(tags, ARTIST_TAG[dotext])

    def _get_title_tag(self, dotext: str, tags: t.Mapping[str, t.Any]) -> str:
        return self._get_tag_value(tags, TITLE_TAG[dotext])

    def _get_album_tag(self, dotext: str, tags: t.Mapping[str, t.Any]) -> str:
        return self._get_tag_value(tags, ALBUM_TAG[dotext])

    def process_local_dir(self, file, local_dir):
        """Extract release data from the release's individual files.

        INTERNAL. Invoked by `ReleaseService` itself when processing a `PREVIEW` request.

        Audio file tags (ID3 for .mp3, Vorbis comment for both .ogg and .opus files) are read in order to
        gather:
          - artist and album
          - title of each track

        If the album name is non-unique across audio files, an error is thrown.

        If the artist name is non-unique across audio files, the `VARIOUS_ARTISTS_NAME` constant (= 'VA') is
        used as the release's artist name.

        Duration of each track is also extracted from the file itself.

        The lexicographic order of audio file names inside the temp directory is assumed to reflect the desired
        track numbering, so audio files should be given as:
            01-<remainder_of_name>.opus
            02-<remainder_of_name>.opus
            ...and so on.

        :param file: Release zip file name
        :param local_dir: Temp directory into which release zip was extracted
        """
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
                _, dotext = os.path.splitext(music_file)
                try:
                    validate_filename(music_file)
                except:
                    # File name is too garbled. Just use number.
                    music_file = f"{i:02}{dotext}"
                player_files.append({
                    "_artist": self._get_artist_tag(dotext, tags),
                    "file": music_file,
                    "number": i,
                    "title": self._get_title_tag(dotext, tags),
                    "duration_secs": round(mf.info.length),  # type: ignore
                    "duration_hms": models.PlayerFile.show_duration(round(mf.info.length)),  # type: ignore
                })
                albums.add(self._get_album_tag(dotext, tags))

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
        """Upload a release's individual files (audio and cover) to the publicly accessible release directory.

        INTERNAL. Invoked by `ReleaseService` itself when processing an `UPLOAD` request.        

        :param file: Release zip file name
        """
        data = self.task_state[RequestType.UPLOAD, file].data
        data["completed_uploads"] = []

        try:
            storage = get_storage_client()
            remote_rlsdir = os.path.join("Releases", data["release_dir"])
            completed_uploads = []
            for local, pf in zip(data["local_files"], data["player_files"]):
                remote = os.path.join(remote_rlsdir, pf["file"])
                log.info(f"ReleaseCreator.upload_player_file | local='{local}' | remote='{remote}'")
                storage.upload(local, remote)
                data["completed_uploads"].append({"from": local, "to": remote})
                time.sleep(0)
            storage.upload(
                os.path.join(data["local_dir"], "cover.jpg"),
                os.path.join(remote_rlsdir, "cover.jpg")
            )
        except Exception as ex:
            self.task_state[RequestType.UPLOAD, file].success = False
            self.task_state[RequestType.UPLOAD, file].exception = ex
            return
        
        self.task_state[RequestType.UPLOAD, file].success = True

    def upload_to_ia(self, file, local_dir):
        """Submit a release to archive.org.

        INTERNAL. Invoked by `ReleaseService` itself when processing an `IA_UPLOAD` request.        
        
        Archive.org submission is handled by [ArchiveOrgClient](archive_org_client.py) and involves generating
        archive.org-specific metadata from the release data, and uploading the individual files.

        :param file: Release zip file name
        :param local_dir: Temp directory into which release zip was extracted
        """
        data = self.task_state[RequestType.IA_UPLOAD, file].data

        try:
            engine = engine_from_config(settings, prefix='sqlalchemy.')
            session = sessionmaker(bind=engine)()
            release = session.query(models.Release).filter(models.Release.file == file).one()
            identifier = ArchiveOrgClient().upload_release(release, local_dir)
        except Exception as ex:
            self.task_state[RequestType.IA_UPLOAD, file].success = False
            self.task_state[RequestType.IA_UPLOAD, file].exception = ex
            return
        
        release.release_data["archive"] = f"https://archive.org/details/{identifier}"
        flag_modified(release, "release_data")
        session.add(release)
        session.commit()

        data.update({
            "identifier": identifier,
            "release_id": int(release.id),  # type: ignore
        })
        self.task_state[RequestType.IA_UPLOAD, file].success = True

    def create_database_objects(self, dbsession, file, page_content, index_record_body):
        """Synchronously insert the rows representing a release into the database.

        This is invoked by the `commit_release` view when user confirms the release should go live after the
        individual files have been uploaded to the release directory.

        :param dbsession: The view passes the request's database session.
        :param file: Release zip file name
        :param page_content: The view passes the release page content as entered by the user.
        :param index_record_body: The view passes the content of the index page entry as entered by the user.
        """
        data = self.task_state[RequestType.UPLOAD, file].data

        release = models.Release(
            catalog_no=data["catalog_no"],
            release_dir=data["release_dir"],
            file=data["file"],
            release_data=data["release_data"],
        )
        dbsession.add(release)
        dbsession.flush()
        data["release_id"] = int(release.id)  # type: ignore

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

    def delete_database_objects(self, dbsession, release_id):
        """Synchronously delete the rows representing a release from the database.

        This is invoked by the `delete_release` view when user clicks the `Delete` button on a row in the
        release list view.

        :param dbsession: The view passes the request's database session.
        :param release_id: Primary key of release in database
        """
        release = dbsession.query(models.Release).filter(models.Release.id == release_id).one()

        # An index record can be associated with multiple releases. This won't be the case for new
        # index records, but there are a few legacy index records that refer to multiple releases. 
        # Delete only index records where this release is the only release referred to.
        q = (
            dbsession.query(models.IndexRecord)
            .filter(models.IndexRecord.releases.contains(release))
            .join(models.IndexRecord.releases)
            .group_by(models.IndexRecord.id)
            .having(func.count(models.Release.id) == 1)
            .with_entities(models.IndexRecord.id)
        )
        index_record_ids = [ir.id for ir in q]

        release.index_records = []
        dbsession.flush()
        dbsession.query(models.IndexRecord).filter(models.IndexRecord.id.in_(index_record_ids)).delete()

        if release.release_page:
            dbsession.query(models.PlayerFile).filter(models.PlayerFile.release_page_id == release.release_page.id).delete()
            dbsession.delete(release.release_page)

        dbsession.delete(release)

@cached(cache={}, key=lambda: "🕉")
def get_release_service():
    return ReleaseService()
