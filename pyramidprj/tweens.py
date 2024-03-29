"""This file contains middlewares that are installed in Pyramid's request/response pipelines.

resolve_release (request middleware):
    Check each request for a URL that points to a release page. When it is a release page URL,
    look up the `Release` object in the database by `release_dir` and attach it to the request.

    
rewrite_links (response middleware):
    The index page as well as some release pages contain links with URLs that aren't valid anymore with
    20kbps_pyramid. These links are rewritten to point to the correct resources. Doing this on-the-fly was a
    design choice that was made in order to preserve legacy documents in their original state, while still
    allowing for them to be patched as needed.
"""
from urllib.parse import unquote, urlparse, urlunparse

from bs4 import BeautifulSoup

from pyramidprj import models

import logging

log = logging.getLogger(__name__)


# rewrite_links middleware is applied to these routes only
REWRITE_FOR_ROUTES = [
    "index2",
    "Releases",
    "Releases_with_subdir",
]


LEGACY_STATIC_FILES = [
    "ico/yikis.jpg",
    "fav/rate_fav.ico",
    "ico/humanstxt-isolated-blank.gif",
    "ico/rate.ico",
    "ico/last-icon.jpg",
    "fav/orgasm.ico",
    "humans.txt",
    "Releases/humans.txt",
    "favicontw.ico",
    "css/relpage.css",
    "fav/digg_favicon.ico",
    "ico/glogo.jpg",
    "record16.ico",
    "ico/download.png",
    "rss.png",
    "Releases/slow-wave-sleep/elogio-della-follia/ITA Lyrics.pdf",
    "fav/tumblr_fav.gif",
    "20kbps.xml",
    "rss/20kbps.xml",
    "favicon_myspace.png",
    "Releases/slow-wave-sleep/elogio-della-follia/ENG Lyrics.pdf",
    "ico/discogs-icon.jpeg",
    "fav/mcfav.png",
]


URL_ATTRIBUTES = {
    "img": ("src",),
    "a": ("href", "src",),
    "link": ("href",),
    "meta": ("content",),
    "iframe": ("src",),
}


def _get_doc_with_links_rewritten(request, response, registry):
    # The `resolve_release` middleware has added release to request, if found.
    release = getattr(request, "release", None)

    try:
        body, encoding = response.body.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        body, encoding = response.body.decode("iso-8859-1"), "iso-8859-1"

    static_base = registry.settings['static_base']
    pr_static_base = urlparse(static_base)

    soup = BeautifulSoup(body, "html5lib")
    for tag, attrs in URL_ATTRIBUTES.items():
        elems = soup.find_all(tag)
        for elem in elems:
            for attr in attrs:
                try:
                    url = elem[attr]
                except KeyError:
                    continue
                pr = urlparse(url)

                # Release pages with `custom_body` (from <release_dir>/index.html)
                # need their cover URL rewritten to point to static asset storage.
                if (
                    release
                    and (pr.path.endswith("cover.jpg") or pr.path.endswith("cover.png"))
                    and pr.netloc != pr_static_base.netloc
                ):
                    elem[attr] = f"{static_base}/Releases/{release.release_dir}/{pr.path.split('/')[-1]}"
                    break

                # Any release archive file URL needs to point to static asset storage.
                if (
                    pr.path.lower().endswith(".zip") or pr.path.lower().endswith(".rar")
                ):
                    elem[attr] = f"{static_base}/Releases/{pr.path.split('/')[-1]}"
                    break

                # Some releases specify a custom player in `release_data["player"]`.
                # The embedded URL must be forced to https.
                if pr.netloc.endswith("archive.org") and pr.scheme == "http":
                    pr = pr._replace(scheme="https")
                    elem[attr] = urlunparse(pr)
                    break

                # Rewrite the obsolete domain to 20kbps.net.
                if pr.netloc == "20kbps.sofapause.ch":
                    pr = pr._replace(netloc="20kbps.net")
                    elem[attr] = urlunparse(pr)

                # Any file in LEGACY_STATIC_FILES must point to static asset storage.
                for file in LEGACY_STATIC_FILES:
                    if pr.path.endswith(file):
                        elem[attr] = f"{static_base}/{file}"
                        break

    return str(soup).encode(encoding)  # type: ignore


def rewrite_links(request, response, registry):
    """
    A lot of the imported HTML has URLs that must be rewritten.
    This middleware takes care of it after a view has been rendered to a response.
    """
    if response.status_code != 200:
        return response

    if (
        request.matched_route is None
        or request.matched_route.name not in REWRITE_FOR_ROUTES
    ):
        return response

    response.body = _get_doc_with_links_rewritten(request, response, registry)
    return response


def resolve_release(request, registry):
    """
    When the URL is for a release page, resolve the `Release` object and add it to the request.
    """
    if request.path[-1] != "/":
        return

    path = request.path[:-1]
    if (
        "/Releases" not in path
        or "." in path.split("/")[-1]
    ):
        return

    rlsdir = unquote(path.replace("/Releases/", ""))

    rls = (
        request.dbsession.query(models.Release)
        .filter(
            models.Release.release_dir == rlsdir
        )
        .first()
    )
    setattr(request, "release", rls)


REQUEST_MIDDLEWARE = [
    resolve_release,
]


RESPONSE_MIDDLEWARE = [
    rewrite_links,
]


def request_middleware_tween_factory(handler, registry):

    def request_middleware_tween(request):
        for middleware in REQUEST_MIDDLEWARE:
            middleware(request, registry)
        response = handler(request)        
        return response

    return request_middleware_tween


def response_middleware_tween_factory(handler, registry):

    def response_middleware_tween(request):
        response = handler(request)        
        for middleware in RESPONSE_MIDDLEWARE:
            response = middleware(request, response, registry)
        return response

    return response_middleware_tween
