from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

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


def rewrite_links(response, registry):
    if response.status_code != 200 or response.content_type != "text/html":
        return response

    try:
        body, encoding = response.body.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        body, encoding = response.body.decode("iso-8859-1"), "iso-8859-1"

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
                        elem[attr] = f"{registry.settings['static_base']}/{file}"
                        break

    response.body = str(soup).encode(encoding)  # type: ignore
    return response


RESPONSE_MIDDLEWARE = [
    rewrite_links,
]


def response_middleware_tween_factory(handler, registry):

    def response_middleware_tween(request):
        response = handler(request)        
        for middleware in RESPONSE_MIDDLEWARE:
            response = middleware(response, registry)
        return response

    return response_middleware_tween
