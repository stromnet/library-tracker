from __future__ import annotations

import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.cookiejar import CookieJar


def _origin(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


@dataclass
class HttpResponse:
    url: str
    body: str


class Session:
    def __init__(self) -> None:
        self._jar = CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar)
        )

    def get(self, url: str, *, referer: str | None = None) -> HttpResponse:
        request = urllib.request.Request(url, headers=self._headers(referer=referer))
        with self._opener.open(request, timeout=30) as response:
            return HttpResponse(
                url=response.geturl(),
                body=response.read().decode("utf-8", "ignore"),
            )

    def post_form(
        self, url: str, data: dict[str, str], *, referer: str | None = None
    ) -> HttpResponse:
        payload = urllib.parse.urlencode(data).encode()
        headers = self._headers(referer=referer)
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Origin"] = _origin(url)
        request = urllib.request.Request(
            url,
            data=payload,
            headers=headers,
        )
        with self._opener.open(request, timeout=30) as response:
            return HttpResponse(
                url=response.geturl(),
                body=response.read().decode("utf-8", "ignore"),
            )

    def _headers(self, *, referer: str | None) -> dict[str, str]:
        headers: dict[str, str] = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
        }
        if referer:
            headers["Referer"] = referer
        return headers
