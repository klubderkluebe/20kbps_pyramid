import glob
import json
import typing as t
from copy import copy

from pyramid.threadlocal import get_current_registry

import internetarchive as ia
import shortuuid

if t.TYPE_CHECKING:
    from .models import Release
    from requests import Response

import logging


log = logging.getLogger(__name__)

settings = get_current_registry().settings


class ArchiveOrgClient:
    def __init__(self):
        with open(settings["archive_org_s3_credentials"], "r") as f:
            credentials = json.loads(f.read())
        self.session = ia.get_session(credentials)
        self.md_template = {
            "mediatype": "audio",
            "collection": (
                list(map(lambda s: s.strip(), settings["archive_org_collections"].split(",")))
            ),
            "subject": "lobit",
            "uploader": settings["archive_org_uploader"],
        }
        
    def release_metadata(self, r: "Release") -> dict:
        md = copy(self.md_template)
        md.update({
            "creator": r.release_data["artist"],  # type: ignore (new releases always have release_data)
            "date": r.release_data["date"],  # type: ignore
            "description": r.release_page.content_text,
            "title": r.release_data["relname"],  # type: ignore            
        })
        return md

    def upload_release(self, r: "Release", local_dir: str, use_uuid: bool = False):
        files = glob.glob(f"{local_dir}/*")
        md = self.release_metadata(r)
        identifier = (
            shortuuid.uuid() if use_uuid else t.cast(str, r.catalog_no)
        )
        log.info(f"upload_release | identifier='{identifier}'")
        item = self.session.get_item(identifier)
        [res, *_] = t.cast(list["Response"], item.upload(files=files, metadata=md))
        if res.status_code != 200:
            raise Exception(f"archive.org upload failed (res.status_code={res.status_code})")
        return identifier
