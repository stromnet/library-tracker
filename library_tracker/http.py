from __future__ import annotations

import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.cookiejar import CookieJar


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
        request = urllib.request.Request(
            url,
            data=payload,
            headers=self._headers(referer=referer),
        )
        with self._opener.open(request, timeout=30) as response:
            return HttpResponse(
                url=response.geturl(),
                body=response.read().decode("utf-8", "ignore"),
            )

    def _headers(self, *, referer: str | None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if referer:
            headers["Referer"] = referer
        return headers
