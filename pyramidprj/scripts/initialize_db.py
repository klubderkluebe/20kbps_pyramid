import argparse
import sys
from string import whitespace

from pyramid.paster import bootstrap, setup_logging
from sqlalchemy.exc import OperationalError

from bs4 import BeautifulSoup

from .. import models


LEGACY_HTTPDOCS_DIRECTOR = "/home/jonas/20kbps/httpdocs"


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
    with open(f"{LEGACY_HTTPDOCS_DIRECTOR}/index2.htm", "r") as f:
        html_doc = f.read()

    soup = BeautifulSoup(html_doc, "html.parser")
    r = soup.find_all(lambda t: t.name == "tr" and t.get("valign", "").lower() == "top")  # type: ignore

    records = [
        {
            "date": rec.find_all("td")[0].text.strip(),
            "body": squash_whitespace(rec.find_all("td")[1].decode_contents().strip()),
        }
        for rec in r
    ]

    for rec in records:
        model = models.index_record.IndexRecord(
            date=rec["date"],
            body=rec["body"],
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
