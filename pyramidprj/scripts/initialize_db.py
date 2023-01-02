import argparse
import glob
import os.path
import re
import sys
from collections import defaultdict
from itertools import chain
from string import whitespace
from urllib.parse import urlparse

from pyramid.paster import bootstrap, setup_logging
from sqlalchemy.exc import OperationalError

import mutagen
from bs4 import BeautifulSoup
from php_whisperer import read_raw

from .. import models


LEGACY_HTTPDOCS_DIRECTORY = ""  # set from settings in main

FILENAME_OVERRIDES = {
    "20k01": "Hakin_Basar_-_Fuck_Fantasy_(20k01)-2002.zip",
    "20k26": "Lukas_Treyer_und_Yann_Blumer_-_Bettmümpfeli_(20k26)-2003.zip",
    "20k030": "Restposten_-_Aufgeräumt_(20k030)-2003.zip",
    "20k032": "Maxi_Single_feat._Afolf_Neger_-_Blütezeit_(20k032)-2003.zip",
    "20k37": "dkvsjt_-_35deg_e.p._(20k37)-2003.zip",
    "20k040": "Haz_und_Laub_-_Birds_Are_Fucking_(20k040)-2003.zip",
    "20k045": "simpler_-_lärmbelästigung_e.p._(20k045)-2003.zip",
    "20k054": "kurmark_-_white_widow_e.p.-(20k054)-2003.zip",
    "20k101": "atarix_and_his_sooperskalar_band_-_snra_a_planet-(20k101)-2004.zip",
    "20k127": "S._Müller_-_BOTattack-(20k127)-2004.zip",
    "20k242": "Sascha_Müller_-_Radioaktivität-(20k242)-2007.zip",
    "20k368": "mauk_tenieb_-_esiön-(20k368)-2021.zip",
}


def squash_whitespace(s):
    t = ""
    squashing = False
    for ch in s:
        if ch in whitespace:
            if not squashing:
                t += ch
                squashing = True
        else:
            t += ch
            squashing = False
    return t


def as_dict(r):
    keys = ["id"] + sorted([k for k in dir(r) if k[0] != "_" and k not in ("metadata", "registry", "id")])
    return {k: getattr(r, k) for k in keys}


def maybenext(it):
    try:
        return next(it)
    except StopIteration:
        return None


def parse_catalogno(s):
    s_i = s.lower().split("k")[1]
    if s_i.isdigit():
        return int(s_i)
    return None


def _get_tracks_by_id3(rlsdir):
    pattern = os.path.join(LEGACY_HTTPDOCS_DIRECTORY, "Releases", rlsdir, "*.mp3")
    files = glob.glob(pattern)
    tracks = []
    for i, f in enumerate(sorted(files)):
        mf = mutagen.File(f)  # type: ignore
        tags = mf.tags  # type: ignore
        tracks.append({
            "number": i + 1,
            "file": f,
            "title": tags.get("TIT2").text[0],
            "duration_secs": round(mf.info.length),  # type: ignore
        })
    return tracks


def setup_player_files(dbsession):
    ptn_tracksarr = re.compile(r'"tracks" => array\((.*)\);', re.DOTALL)
    ptn_track = re.compile(r'new track\(.*?"(.*?)".*?,.*?"(.*?)".*?,.*?"(\d*)".*?\)', re.DOTALL)

    query = dbsession.query(models.ReleasePage)
    pages = query.all()
    for pg in pages:
        if pg.custom_body:
            # Pages imported from index.html don't have players.
            continue

        with open(f"{LEGACY_HTTPDOCS_DIRECTORY}/Releases/{pg.release.release_dir}/release.php", "r") as f:
            release_php = f.read()

        m = ptn_tracksarr.search(release_php)
        if m:                    
            s_tracksarr = m.groups()[0]  # type: ignore
            tracks = [
                {
                    "number": i + 1,
                    "file": t[1],
                    "title": t[0],
                    "duration_secs": int(t[2]) if t[2] else None,
                }
                for i, t in enumerate(ptn_track.findall(s_tracksarr))
            ]
        else:
            tracks = _get_tracks_by_id3(pg.release.release_dir)

        for t in tracks:
            model = models.PlayerFile(
                release_page=pg,
                file=t["file"],
                number=t["number"],
                title=t["title"],
                duration_secs=t["duration_secs"]
            )
            dbsession.add(model)

    dbsession.flush()


def _get_release_data(rlsdir):
    release_php_file = os.path.join(LEGACY_HTTPDOCS_DIRECTORY, "Releases", rlsdir, "release.php")
    if not os.path.exists(release_php_file):
        return dict()

    with open(release_php_file, "r") as f:
        release_php = f.read()

    ptn_release = re.compile(r"\$release = array\(.*?\);", re.DOTALL)
    ptn_tracksarr = re.compile(r',\s*"tracks" => array\((.*)\);', re.DOTALL)
    ptn_recomsarr = re.compile(r'"recommendations" => array\(.*?\),\s*"', re.DOTALL)
    ptn_recom = re.compile(r'new recommendation\("(.*?)",\s*"(.*?)"\)')

    m = ptn_release.search(release_php)
    release_assoc_arr = release_php[m.start():m.end()]  # type: ignore

    recommendations = None
    m = ptn_recomsarr.search(release_assoc_arr)    
    if m:
        recommendations_arr = release_assoc_arr[m.start():m.end()]
        recommendations = [
            {"by": by, "url": url}
            for (by, url) in ptn_recom.findall(recommendations_arr)
        ]
        release_assoc_arr = release_assoc_arr[:m.start()] + release_assoc_arr[m.end() - 1:]

    m = ptn_tracksarr.search(release_assoc_arr)
    if m:
        release_assoc_arr = release_assoc_arr[:m.start()] + release_assoc_arr[m.end() - 2:]

    data = read_raw("<?php\n" + release_assoc_arr, "release")
    if recommendations:
        data["recommendations"] = recommendations

    return data


def setup_release_pages(dbsession):
    query = dbsession.query(models.Release)
    releases = query.all()
    for r in releases:
        if not r.release_dir:
            continue

        rlsdir = os.path.join(LEGACY_HTTPDOCS_DIRECTORY, "Releases", r.release_dir)
        pr_text_file = os.path.join(rlsdir, "pr-text.inc.php")
        index_file = os.path.join(rlsdir, "index.html")        

        is_pr_text, body_file = (
            (True, pr_text_file) if os.path.exists(pr_text_file)
            else (False, index_file)
        )
        try:
            with open(body_file, "r", encoding="utf-8") as f:
                body = f.read()
        except UnicodeDecodeError:
            with open(body_file, "r", encoding="iso-8859-1") as f:
                body = f.read()

        r.release_data = _get_release_data(r.release_dir)

        model = models.ReleasePage(
            release=r,
            content=body if is_pr_text else None,
            custom_body=body if not is_pr_text else None,
        )
        dbsession.add(model)
    
    dbsession.flush()


def setup_releases(dbsession):
    BODY_20K51 = "sita_-_einige_tracks_fuer_gert_von_heinz-(20k051)-2003"
    FILE_20K281 = "Releases/I_HATE_THIS_ARCHIVE.RAR"
    FILE_20K328 = "Releases/origami_repetika_-_pharmaceutically_damaged-(20k238)-2011.zip"

    ptn_20kx = re.compile(r"\(([23][09][kK].*?)\)")
    ptn_rlsdir = re.compile(r"Releases/(.*)")
    ptn_php20kx = re.compile(r'"cat-no" => "(.*?)"')
    ptn_phpdl = re.compile(r'"download" => "(.*?)"')
    ptn_html20kx = re.compile(r"\b(20k.*?) \|")

    all_releases = []

    query = dbsession.query(models.IndexRecord)
    records = query.all()
    for rec in records:
        soup = BeautifulSoup(rec.body, "html.parser")
        anchors = soup.find_all("a")
        hrefs = {a["href"] for a in anchors}
        anchor_texts = [a.text for a in anchors]
        archive_hrefs = [h for h in hrefs if h.lower().endswith(".zip") or h.lower().endswith(".rar")]
        catalog_nos = set(chain.from_iterable(
            ptn_20kx.findall(h) for h in archive_hrefs + anchor_texts
        ))

        if archive_hrefs and archive_hrefs[0] == FILE_20K328:
            releases = {
                "20k328": {"index_record_ids": [rec.id], "file": FILE_20K328}
            }
        elif rec.body.startswith(BODY_20K51):
            releases = {
                "20k51": {"index_record_ids": [rec.id], "file": f"{BODY_20K51}.zip"}
            }
        else:
            releases = defaultdict(dict,
                {
                    catalog_no: {
                        "index_record_ids": [rec.id],
                        "file": (
                            maybenext(h for h in archive_hrefs if catalog_no in h)
                            or (
                                FILE_20K281
                                if archive_hrefs[0] == FILE_20K281
                                else None
                            )
                        )
                    }
                    for catalog_no in catalog_nos
                }
            )

            rls_hrefs = [h for h in hrefs if "Releases/" in h]
            for h in set(rls_hrefs) - set(archive_hrefs):
                pr = urlparse(h)
                rlsdir = ptn_rlsdir.search(pr.path).groups()[0]  # type: ignore
                try:
                    release_php_file = os.path.join(LEGACY_HTTPDOCS_DIRECTORY, "Releases", rlsdir, "release.php")
                    with open(release_php_file, "r") as f:
                        release_php = f.read()
                    file = ptn_phpdl.search(release_php).groups()[0]  # type: ignore
                    catalog_no = ptn_php20kx.search(release_php).groups()[0]  # type: ignore
                    catalog_nos.add(catalog_no)                
                except FileNotFoundError:
                    release_index_file = os.path.join(LEGACY_HTTPDOCS_DIRECTORY, "Releases", rlsdir, "index.html")
                    with open(release_index_file, "r", encoding="iso-8859-1") as f:
                        release_html = f.read()
                    soup = BeautifulSoup(release_html, "html.parser")
                    file = next(a["href"] for a in soup.find_all("a") if a["href"].lower().endswith(".zip"))
                    catalog_no = ptn_html20kx.search(release_html).groups()[0]  # type: ignore
                    catalog_nos.add(catalog_no)  # type: ignore

                releases[catalog_no].update({
                    "index_record_ids": [rec.id],
                    "file": releases[catalog_no].get("file", file),
                    "release_dir": rlsdir,
                })

        all_releases.extend([
            {
                "catalog_no": catalog_no,
                **rls
            }
            for catalog_no, rls in releases.items()
            if rls["file"]
        ])

    unique_catalog_nos = {r["catalog_no"] for r in all_releases if r["catalog_no"] not in ("29k359", "20kFF35")}
    all_releases_unique_catalog_no = []
    for catalog_no in unique_catalog_nos:
        matches = [r for r in all_releases if r["catalog_no"] == catalog_no]
        index_record_ids = list(chain.from_iterable(m["index_record_ids"] for m in matches))
        melt = dict()
        for m in matches:
            melt.update(m)
        melt["index_record_ids"] = index_record_ids
        melt["file"] = FILENAME_OVERRIDES.get(catalog_no, melt["file"].split("/")[-1])
        all_releases_unique_catalog_no.append(melt)

    all_releases = sorted(
        all_releases_unique_catalog_no,
        key=lambda r: (
            1_000 + parse_catalogno(r["catalog_no"])  # type: ignore
            if parse_catalogno(r["catalog_no"])
            else 327 - max(r["index_record_ids"])
        )
    )

    for r in all_releases:
        index_records = (
            dbsession.query(models.IndexRecord)
            .filter(models.IndexRecord.id.in_(r["index_record_ids"]))
            .all()
        )

        if "release_dir" in r:
            release_dir = (
                r["release_dir"][:-1] if r["release_dir"][-1] == "/"
                else r["release_dir"]
            )
        else:
            release_dir = None

        model = models.Release(
            catalog_no=r["catalog_no"],
            release_dir=release_dir,
            file=r["file"],
            index_records=index_records,
        )
        dbsession.add(model)
    
    dbsession.flush()


def setup_index_records(dbsession):
    """
    Add or update models / fixtures in the database.

    """
    with open(f"{LEGACY_HTTPDOCS_DIRECTORY}/index2.htm", "r") as f:
        html_doc = f.read()

    soup = BeautifulSoup(html_doc, "html.parser")
    r = soup.find_all(lambda t: t.name == "tr" and t.get("valign", "").lower() == "top")  # type: ignore

    records = []
    for rec in r:
        tds = rec.find_all("td")
        td0, td1 = tds[0], tds[1]
        asdict = {
            "date": td0.text.strip(),
            "body": squash_whitespace(td1.decode_contents().strip()),
            "explicit_height": (
                int(td0["height"])
                if td0.get("height", None)
                else None
            ),
        }

        if len(td0.find_all(recursive=False)) > 1:
            asdict["custom_date_section"] = squash_whitespace(td0.decode_contents().strip())

        records.append(asdict)

    for rec in records:
        model = models.IndexRecord(
            date=rec["date"],
            body=rec["body"],
            explicit_height=rec["explicit_height"],
            custom_date_section=rec.get("custom_date_section", None)
        )
        dbsession.add(model)

    dbsession.flush()


def setup_models(dbsession):
    setup_index_records(dbsession)
    setup_releases(dbsession)
    setup_release_pages(dbsession)
    setup_player_files(dbsession)


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'config_uri',
        help='Configuration file, e.g., development.ini',
    )
    return parser.parse_args(argv[1:])


def main(argv=sys.argv):
    global LEGACY_HTTPDOCS_DIRECTORY

    args = parse_args(argv)
    setup_logging(args.config_uri)
    env = bootstrap(args.config_uri)

    LEGACY_HTTPDOCS_DIRECTORY = env["registry"].settings["legacy_httpdocs_directory"]

    try:
        with env['request'].tm:
            dbsession = env['request'].dbsession
            setup_models(dbsession)
    except OperationalError:
        print('''
Pyramid is having a problem using your SQL database.  The problem
might be caused by one of the following things:

1.  You may need to initialize your database tables with `alembic`.
    Check your README.txt for description and try to run it.

2.  Your database server may not be running.  Check that the
    database server referred to by the "sqlalchemy.url" setting in
    your "development.ini" file is running.
            ''')
