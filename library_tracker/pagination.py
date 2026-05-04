from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, urljoin, urlparse

from .http import Session


def fetch_paginated_pages(
    session: Session,
    first_url: str,
    first_body: str,
    *,
    referer: str | None = None,
    max_pages: int = 10,
) -> list[str]:
    pages = [first_body]
    seen = {first_url}
    queue = [first_url]

    while queue and len(seen) < max_pages:
        current_url = queue.pop(0)
        current_body = pages[-1] if current_url == first_url else session.get(current_url, referer=referer).body
        for link in _extract_page_links(current_body, current_url):
            if link not in seen:
                seen.add(link)
                queue.append(link)
                pages.append(session.get(link, referer=current_url).body)
                if len(seen) >= max_pages:
                    break
    return pages


def _extract_page_links(page: str, current_url: str) -> list[str]:
    current = urlparse(current_url)
    links: list[str] = []
    for match in re.finditer(r'href=["\']([^"\']+)["\']', page, re.IGNORECASE):
        href = html.unescape(match.group(1))
        absolute = urljoin(current_url, href)
        parsed = urlparse(absolute)
        if parsed.netloc != current.netloc:
            continue
        if parsed.path != current.path:
            continue
        if absolute == current_url:
            continue
        query = parse_qs(parsed.query)
        if any(key in query for key in ["page", "start", "offset"]):
            links.append(absolute)
    return list(dict.fromkeys(links))


def extract_wicket_next_url(portlet_html: str) -> str | None:
    match = re.search(
        r"wicketAjaxGet\('([^']+)'[^>]+Gå till nästa sida",
        portlet_html,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return html.unescape(match.group(1))
    match = re.search(
        r'title="Gå till nästa sida"[^>]+onclick="[^"]*wicketAjaxGet\(\'([^\']+)\'',
        portlet_html,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return html.unescape(match.group(1))
    return None


def extract_wicket_component_html(response_body: str, component_hint: str) -> str | None:
    if "<![CDATA[" not in response_body:
        return None
    pattern = rf'<component[^>]+id="[^"]*{re.escape(component_hint)}[^"]*"[^>]*><!\[CDATA\[(.*?)\]\]></component>'
    match = re.search(pattern, response_body, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1)
    generic = re.search(r'<!\[CDATA\[(.*)\]\]>', response_body, re.IGNORECASE | re.DOTALL)
    return generic.group(1) if generic else None
