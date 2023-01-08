from pyramid.authentication import BasicAuthAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.config import Configurator
from pyramid.httpexceptions import (
    HTTPForbidden,
    HTTPNotFound,
    HTTPUnauthorized,
)
from pyramid.httpexceptions import HTTPUnauthorized
from pyramid.security import ALL_PERMISSIONS
from pyramid.security import Allow
from pyramid.security import Authenticated
from pyramid.security import forget
from pyramid.view import forbidden_view_config
from pyramid.view import view_config

from . import models


@forbidden_view_config()
def forbidden_view(request):
    if request.authenticated_userid is None:
        response = HTTPUnauthorized()
        response.headers.update(forget(request))

    # user is logged in but doesn't have permissions, reject wholesale
    else:
        response = HTTPForbidden()
    return response


def check_credentials(username, password, request):
    if username == 'admin' and password == 'admin':
        # an empty list is enough to indicate logged-in... watch how this
        # affects the principals returned in the home view if you want to
        # expand ACLs later
        return []


class Root:
    # dead simple, give everyone who is logged in any permission
    __acl__ = (
        (Allow, Authenticated, ALL_PERMISSIONS),
    )


def notfound(request):
    return HTTPNotFound()


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    with Configurator(settings=settings) as config:

        authn_policy = BasicAuthAuthenticationPolicy(check_credentials)
        config.set_authentication_policy(authn_policy)
        config.set_authorization_policy(ACLAuthorizationPolicy())
        config.set_root_factory(lambda request: Root())

        config.include('pyramid_nacl_session')        
        config.include('pyramid_jinja2')
        config.include('.routes')
        config.include('.models')
        config.scan()
        config.add_tween("pyramidprj.tweens.request_middleware_tween_factory", under="pyramid_tm.tm_tween_factory")
        config.add_tween("pyramidprj.tweens.response_middleware_tween_factory", under="pyramidprj.tweens.request_middleware_tween_factory")
    return config.make_wsgi_app()
