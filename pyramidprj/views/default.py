import json
import os.path

import pyramid.httpexceptions as exc
from pyramid.renderers import render_to_response
from pyramid.response import FileResponse, Response
from pyramid.view import view_config
from sqlalchemy.exc import SQLAlchemyError

import requests
import zipfile

from .. import models
from ..release_creator import ReleaseCreator

import logging

log = logging.getLogger(__name__)


@view_config(route_name="home", renderer="pyramidprj:templates/index.jinja2")
def index(request):
    return {}


@view_config(route_name='index2', renderer='pyramidprj:templates/index2.jinja2')
def index2(request):
    try:
        query = request.dbsession.query(models.IndexRecord)
        records = query.all()
    except SQLAlchemyError:
        return Response(db_err_msg, content_type='text/plain', status=500)

    return {"records": records}


@view_config(route_name="create_release", renderer="pyramidprj:templates/create_release.jinja2", permission="🕉")
def create_release(request):
    return {}


@view_config(route_name="post_new_release_file", request_method="POST", renderer="pyramidprj:templates/post_new_release_file.jinja2", permission="🕉")
def post_new_release_file(request):
    tmpdir = request.registry.settings["tmp_directory"]
    file = request.POST['file']
    local_dir = os.path.join(tmpdir, file.replace(".zip", ""))

    if not os.path.exists(local_dir):
        res = requests.get(
            f"{request.registry.settings['static_base']}/Releases/{file}"
        )
        local_file = os.path.join(tmpdir, file)
        with open(local_file, "wb") as f:
            f.write(res.content)
        with zipfile.ZipFile(local_file, "r") as f:
            f.extractall(local_dir)

    data = ReleaseCreator(local_dir).process_local_dir()
    request.session["new_release"] = data
    return data


@view_config(route_name="confirm_new_release", request_method="POST", renderer="pyramidprj:templates/confirm_new_release.jinja2", permission="🕉")
def confirm_new_release(request):
    rc = ReleaseCreator.from_data(request.session["new_release"])
    rc.create(request.dbsession, request.POST["release_page_content"], request.POST["index_record_body"])
    return {}


@view_config(route_name='Releases')
@view_config(route_name="Releases_with_subdir")
def Releases(request):
    # The `resolve_release` middleware has added release to request, if found.
    release = getattr(request, "release", None)
    release_page = release.release_page if release else None

    if not release_page:
        raise exc.HTTPNotFound()

    if release_page.custom_body:
        return Response(body=release_page.custom_body)
    
    return render_to_response(
        "pyramidprj:templates/release_page.jinja2",
        {
            "release_page": release_page,
            "release": release_page.release,
            "data": release_page.release.release_data,
            "enumerate": enumerate,
            "static_base": request.registry.settings["static_base"],
            "static_dir": (
                os.path.join(request.registry.settings["static_base"], "Releases", release_page.release.release_dir)
            ),
            "join": os.path.join,
        }
    )


db_err_msg = """\
Pyramid is having a problem using your SQL database.  The problem
might be caused by one of the following things:

1.  You may need to initialize your database tables with `alembic`.
    Check your README.txt for descriptions and try to run it.

2.  Your database server may not be running.  Check that the
    database server referred to by the "sqlalchemy.url" setting in
    your "development.ini" file is running.

After you fix the problem, please restart the Pyramid application to
try it again.
"""
