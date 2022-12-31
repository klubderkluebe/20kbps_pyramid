import argparse
import sys
from string import whitespace

from pyramid.paster import bootstrap, setup_logging
from sqlalchemy.exc import OperationalError

from bs4 import BeautifulSoup

from .. import models


LEGACY_HTTPDOCS_DIRECTORY = "/home/jonas/20kbps/httpdocs"


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


def setup_models(dbsession):
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
        model = models.index_record.IndexRecord(
            date=rec["date"],
            body=rec["body"],
            explicit_height=rec["explicit_height"],
            custom_date_section=rec.get("custom_date_section", None)
        )
        dbsession.add(model)


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'config_uri',
        help='Configuration file, e.g., development.ini',
    )
    return parser.parse_args(argv[1:])


def main(argv=sys.argv):
    args = parse_args(argv)
    setup_logging(args.config_uri)
    env = bootstrap(args.config_uri)

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
