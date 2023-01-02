from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

import logging

log = logging.getLogger(__name__)


def rewrite_links(response):
    if response.status_code != 200 or response.content_type != "text/html":
        return response

    try:
        body, encoding = response.body.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        body, encoding = response.body.decode("iso-8859-1"), "iso-8859-1"

    soup = BeautifulSoup(body, "html.parser")
    for a in soup.find_all("a"):
        pr = urlparse(a["href"])
        if pr.netloc == "20kbps.sofapause.ch":
            pr = pr._replace(netloc="20kbps.net")
            a["href"] = urlunparse(pr)

    response.body = soup.html.encode(encoding)  # type: ignore
    return response


RESPONSE_MIDDLEWARE = [
    rewrite_links,
]


def response_middleware_tween_factory(handler, registry):

    def response_middleware_tween(request):
        response = handler(request)        
        for middleware in RESPONSE_MIDDLEWARE:
            response = middleware(response)
        return response

    return response_middleware_tween
