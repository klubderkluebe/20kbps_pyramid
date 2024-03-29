import json
import os.path
import re
from datetime import date

import pyramid.httpexceptions as exc
from pyramid.renderers import render_to_response
from pyramid.response import Response
from pyramid.view import view_config
from sqlalchemy.exc import SQLAlchemyError

from .. import models
from ..release_service import RequestType, get_release_service

import logging

log = logging.getLogger(__name__)


@view_config(route_name="home", renderer="pyramidprj:templates/index.jinja2")
def index(request):
    return {}


@view_config(route_name='index2', renderer='pyramidprj:templates/index2.jinja2')
def index2(request):
    try:
        query = request.dbsession.query(models.IndexRecord).order_by(models.IndexRecord.id.desc())
        records = query.all()
    except SQLAlchemyError:
        return Response(db_err_msg, content_type='text/plain', status=500)

    return {"records": records}


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


@view_config(route_name="create_release", renderer="pyramidprj:templates/create_release.jinja2", permission="🕉")
def create_release(request):
    return {}


@view_config(route_name="request_preview", request_method="POST", renderer="pyramidprj:templates/request_preview.jinja2", permission="🕉")
def request_preview(request):    
    file = request.POST['file']
    key = (RequestType.PREVIEW, file)

    m = re.search(r"(?:(?!_-_)[^\s])*_-_.*-\(([\w-]+)\)-\d{4}\.zip", file)
    if not m:
        raise exc.HTTPBadRequest("Filename given does not match pattern artist_name_-_album_name-(catalog_no)-year.zip")
    file = m[0]
    
    release_service = get_release_service()
    task_state = release_service.task_state.get(key)
    if task_state and task_state.success is None:
        raise exc.HTTPBadRequest(f"Preview task for '{file}' is already running")

    if task_state:
        del release_service.task_state[key]

    release_service.request_preview(file)

    return {"file": file}


@view_config(route_name="preview_release", renderer="pyramidprj:templates/preview_release.jinja2", permission="🕉")
def preview_release(request):
    file = request.matchdict["file"]
    key = (RequestType.PREVIEW, file)

    release_service = get_release_service()
    task_state = release_service.task_state.get(key)
    if task_state is None:
        raise exc.HTTPBadRequest(f"There is no preview task for '{file}'")

    return task_state.serialize()


@view_config(route_name="request_upload", request_method="POST", renderer="pyramidprj:templates/request_upload.jinja2", permission="🕉")
def request_upload(request):    
    file = request.POST["file"]
    key = (RequestType.UPLOAD, file)

    release_service = get_release_service()
    task_state = release_service.task_state.get(key)
    if task_state and task_state.success is None:
        raise exc.HTTPBadRequest("Upload task for '{file}' is already running")

    if task_state:
        del release_service.task_state[key]

    release_service.request_upload(file)

    return {"file": file}


@view_config(route_name="check_upload", renderer="pyramidprj:templates/check_upload.jinja2", permission="🕉")
def check_upload(request):
    file = request.matchdict["file"]
    key = (RequestType.UPLOAD, file)

    release_service = get_release_service()
    task_state = release_service.task_state.get(key)
    if task_state is None:
        raise exc.HTTPBadRequest(f"There is no upload task for '{file}'")

    return task_state.serialize()


@view_config(route_name="commit_release", request_method="POST", renderer="pyramidprj:templates/commit_release.jinja2", permission="🕉")
def commit_release(request):    
    file = request.POST["file"]
    key = (RequestType.UPLOAD, file)

    release_service = get_release_service()
    task_state = release_service.task_state.get(key)
    if task_state is None:
        raise exc.HTTPBadRequest(f"There is no upload task for '{file}'")

    if task_state.success is None:
        raise exc.HTTPBadRequest(f"The upload is still pending.")

    release_service.create_database_objects(
        request.dbsession,
        file,
        request.POST["page_content"],
        request.POST["index_record_body"]
    )

    data = task_state.serialize()
    del release_service.task_state[key]
    return data


@view_config(route_name="request_iaupload", request_method="POST", permission="🕉")
def request_iaupload(request):
    file = request.POST["file"]
    key = (RequestType.IA_UPLOAD, file)

    release_service = get_release_service()
    task_state = release_service.task_state.get(key)
    if task_state and task_state.success is None:
        raise exc.HTTPBadRequest("Archive.org upload task for '{file}' is already running")

    if task_state:
        del release_service.task_state[key]

    release_service.request_ia_upload(file)

    return exc.HTTPNoContent()


@view_config(route_name="check_iaupload", renderer="pyramidprj:templates/check_iaupload.jinja2", permission="🕉")
def check_iaupload(request):
    file = request.matchdict["file"]
    key = (RequestType.IA_UPLOAD, file)

    release_service = get_release_service()
    task_state = release_service.task_state.get(key)
    if task_state is None:
        raise exc.HTTPBadRequest(f"There is no archive.org upload task for '{file}'")

    return task_state.serialize()


@view_config(route_name="release_list", renderer="pyramidprj:templates/release_list.jinja2", permission="🕉")
@view_config(route_name="Release_list", renderer="pyramidprj:templates/release_list.jinja2", permission="🕉")
def release_list(request):
    releases = request.dbsession.query(models.Release).order_by(models.Release.id.desc())
    return {
        "releases": releases,
        "authorization": request.headers["Authorization"],
    }


@view_config(route_name='Releases', request_method="DELETE", permission="🕉")
@view_config(route_name="Releases_with_subdir", request_method="DELETE", permission="🕉")
def delete_release(request):
    release = getattr(request, "release", None)
    if release is None:
        raise exc.HTTPBadGateway("No such release")

    get_release_service().delete_database_objects(request.dbsession, release.id)
    return exc.HTTPNoContent()


@view_config(route_name="release_edit", renderer="pyramidprj:templates/release_edit.jinja2", permission="🕉")
def release_edit(request):
    release_id = int(request.matchdict["release_id"])
    release = request.dbsession.query(models.Release).filter(models.Release.id == release_id).one()    
    return {
        "release": release,
        "authorization": request.headers["Authorization"],
        "dumps": json.dumps,
    }


@view_config(route_name="update_release", request_method="POST", permission="🕉")
def update_release(request):
    release_id = int(request.POST["release_id"])
    release_data = json.loads(request.POST["release_data"]) if request.POST["release_data"] else None
    page_content = request.POST["page_content"].strip() or None
    custom_body = request.POST["custom_body"].strip() or None
    index_record_bodies = {}
    for k in [k for k in request.POST.keys() if k.startswith("index_record_body")]:
        ir_id = int(k.split("__")[1])
        index_record_bodies[ir_id] = request.POST[k].strip() or None

    if release_data:
        release = request.dbsession.query(models.Release).filter(models.Release.id == release_id).one()
        release.release_data = release_data
        release.release_page.content = page_content
        release.release_page.custom_body = custom_body

        for ir_id, body in index_record_bodies.items():
            ir = request.dbsession.query(models.IndexRecord).filter(models.IndexRecord.id == ir_id).one()
            ir.body = body

    return exc.HTTPTemporaryRedirect(f"/edit/{release_id}/")


@view_config(route_name="index_record_list", renderer="pyramidprj:templates/index_record_list.jinja2", permission="🕉")
def index_record_list(request):
    index_records = request.dbsession.query(models.IndexRecord).order_by(models.IndexRecord.id.desc())
    return {
        "index_records": index_records,
        "authorization": request.headers["Authorization"],
    }


@view_config(route_name="delete_index_record", request_method="DELETE", permission="🕉")
def delete_index_record(request):
    ir_id = int(request.matchdict["index_record_id"])
    request.dbsession.query(models.IndexRecord).filter(models.IndexRecord.id == ir_id).delete()
    return exc.HTTPNoContent()


@view_config(route_name="index_record_edit", renderer="pyramidprj:templates/index_record_edit.jinja2", permission="🕉")
def index_record_edit(request):
    ir_id = int(request.matchdict["index_record_id"])
    index_record = request.dbsession.query(models.IndexRecord).filter(models.IndexRecord.id == ir_id).one()    
    return {
        "index_record": index_record,
    }


@view_config(route_name="upsert_index_record", request_method="POST", permission="🕉")
def upsert_index_record(request):
    ir_id = int(request.POST["index_record_id"])
    if ir_id == -1:
        ir = models.IndexRecord()
        request.dbsession.add(ir)
    else:
        ir = request.dbsession.query(models.IndexRecord).filter(models.IndexRecord.id == ir_id).one()
    ir.date = request.POST["date"]
    ir.body = request.POST["body"]
    if ir_id == -1:
        request.dbsession.flush()
    return exc.HTTPTemporaryRedirect(f"/edit_index_record/{ir.id}/")


@view_config(route_name="index_record_create", renderer="pyramidprj:templates/index_record_create.jinja2", permission="🕉")
def index_record_create(request):
    return {
        "date_prefill": date.today().strftime("%d. %b %y"),
    }


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
