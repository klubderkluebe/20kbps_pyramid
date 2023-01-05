from urllib.parse import urlparse, urlunparse, urlunsplit

from bs4 import BeautifulSoup

from pyramidprj import models

import logging

log = logging.getLogger(__name__)


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


def rewrite_links(request, response, registry):
    if response.status_code != 200 or response.content_type != "text/html":
        return response

    release = getattr(request, "release", None)

    try:
        body, encoding = response.body.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        body, encoding = response.body.decode("iso-8859-1"), "iso-8859-1"

    static_base = registry.settings['static_base']
    pr_static_base = urlparse(static_base)

    soup = BeautifulSoup(body, "html.parser")
    for tag, attrs in URL_ATTRIBUTES.items():
        elems = soup.find_all(tag)
        for elem in elems:
            for attr in attrs:
                try:
                    url = elem[attr]
                except KeyError:
                    continue
                pr = urlparse(url)

                if (
                    release
                    and (pr.path.endswith("cover.jpg") or pr.path.endswith("cover.png"))
                    and pr.netloc != pr_static_base.netloc
                ):
                    elem[attr] = f"{static_base}/Releases/{release.release_dir}/{pr.path.split('/')[-1]}"
                    break

                if (
                    pr.path.lower().endswith(".zip") or pr.path.lower().endswith(".rar")
                ):
                    elem[attr] = f"{static_base}/Releases/{pr.path.split('/')[-1]}"
                    break

                if pr.netloc.endswith("archive.org") and pr.scheme == "http":
                    pr = pr._replace(scheme="https")
                    elem[attr] = urlunparse(pr)
                    break

                if pr.netloc == "20kbps.sofapause.ch":
                    pr = pr._replace(netloc="20kbps.net")
                    elem[attr] = urlunparse(pr)
                for file in LEGACY_STATIC_FILES:
                    if pr.path.endswith(file):
                        log.info(f"rewrite {file}")
                        elem[attr] = f"{static_base}/{file}"
                        break

    response.body = str(soup).encode(encoding)  # type: ignore
    return response


def resolve_release(request, registry):
    if request.path[-1] != "/":
        return

    path = request.path[:-1]
    if (
        "/Releases" not in path
        or "." in path.split("/")[-1]
    ):
        return

    rlsdir = path.replace("/Releases/", "")
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
