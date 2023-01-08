import glob
import itertools
import os.path
import re
import unicodedata
from datetime import datetime

import mutagen
from pathvalidate import validate_filename

from . import models
from .storage_client import get_storage_client

import logging

log = logging.getLogger(__name__)


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


class ReleaseCreator:
    def __init__(self, local_dir):
        self.local_dir = local_dir
        self.data = {}

    @classmethod
    def from_data(cls, data: dict):
        rc = ReleaseCreator(data["local_dir"])
        rc.data = data
        return rc

    def process_local_dir(self):
        self.data = {
            "local_dir": self.local_dir,
            "catalog_no": ptn_catno.search(self.local_dir).groups()[0],  # type: ignore
            "file": os.path.basename(f"{self.local_dir}.zip"),
        }

        music_files = sorted(list(itertools.chain.from_iterable(
            glob.glob(f"{self.local_dir}/*.{ext}")
            for ext in MUSIC_EXTENSIONS
        )))

        assert glob.glob(f"{self.local_dir}/cover.jpg"), "Missing cover.jpg"

        player_files = []
        albums = set()
        for i, f in enumerate(music_files, 1):
            mf = mutagen.File(f)  # type: ignore
            tags = mf.tags  # type: ignore
            file = sanitize(os.path.basename(f))
            try:
                validate_filename(file)
            except:
                # File name is too garbled. Just use number.
                _, dotext = os.path.splitext(file)
                file = f"{i:02}{dotext}"
            player_files.append({
                "_artist": str(tags[ARTIST_TAG]),
                "file": file,
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

        self.data.update({
            "local_files": music_files,
            "release_dir": os.path.join(sanitize(artist.lower()), sanitize(album.lower())),
            "release_data": {
                "relname": album,
                "artist": artist,
                "cat-no": self.data["catalog_no"],
                "description": f"{artist} - {album} ({self.data['catalog_no']})",
                "list": "ol",
                "date": datetime.now().isoformat()[:10],
            },
            "player_files": player_files,
        })

        return self.data

    def create(self, dbsession, page_content, index_record_body):
        storage = get_storage_client()
        remote_rlsdir = os.path.join("Releases", self.data["release_dir"])

        if not storage.exists(os.path.join(remote_rlsdir, "cover.jpg")):
            for local, pf in zip(self.data["local_files"], self.data["player_files"]):
                remote = os.path.join(remote_rlsdir, pf["file"])
                storage.upload(local, remote)
            storage.upload(
                os.path.join(self.data["local_dir"], "cover.jpg"),
                os.path.join(remote_rlsdir, "cover.jpg")
            )

        release = models.Release(
            catalog_no=self.data["catalog_no"],
            release_dir=self.data["release_dir"],
            file=self.data["file"],
            release_data=self.data["release_data"],
        )
        dbsession.add(release)
        dbsession.flush()

        rp = models.ReleasePage(
            release=release,
            content=page_content,
        )
        dbsession.add(rp)
        dbsession.flush()

        for pf in self.data["player_files"]:
            pf = models.PlayerFile(
                release_page=rp,
                file=pf["file"],
                number=pf["number"],
                title=pf["title"],
                duration_secs=pf["duration_secs"],
            )
            dbsession.add(pf)
        dbsession.flush()