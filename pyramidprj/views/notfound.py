from pyramid.view import notfound_view_config


@notfound_view_config(renderer='pyramidprj:templates/404.jinja2', append_slash=True)
def notfound_view(request):
    request.response.status = 404
    return {}
