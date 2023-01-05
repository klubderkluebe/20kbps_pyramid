import os.path

import pyramid.httpexceptions as exc
from pyramid.renderers import render_to_response
from pyramid.response import FileResponse, Response
from pyramid.view import view_config
from sqlalchemy.exc import SQLAlchemyError

from .. import models

import logging

log = logging.getLogger(__name__)


@view_config(route_name='index2', renderer='pyramidprj:templates/index2.jinja2')
def index2(request):
    try:
        query = request.dbsession.query(models.IndexRecord)
        records = query.all()
    except SQLAlchemyError:
        return Response(db_err_msg, content_type='text/plain', status=500)

    return {"records": records}


def serve_file(file):
    response = FileResponse("/home/jonas/pyramidprj/README.txt")
    response.headers["Content-Disposition"] = f"attachment; filename={file}"
    return response


@view_config(route_name='Releases')
@view_config(route_name="Releases_with_subdir")
def Releases(request):
    rlsdir_or_file = request.matchdict["rlsdir_or_file"]
    if rlsdir_or_file.lower().endswith(".zip") or rlsdir_or_file.lower().endswith(".rar"):
        return serve_file(rlsdir_or_file)

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
