from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPNotFound


def notfound(request):
    return HTTPNotFound()


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    with Configurator(settings=settings) as config:
        config.include('pyramid_jinja2')
        config.include('.routes')
        config.include('.models')
        config.scan()
        config.add_tween("pyramidprj.tweens.request_middleware_tween_factory", under="pyramid_tm.tm_tween_factory")
        config.add_tween("pyramidprj.tweens.response_middleware_tween_factory", under="pyramidprj.tweens.request_middleware_tween_factory")
    return config.make_wsgi_app()
