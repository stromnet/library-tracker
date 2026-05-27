from __future__ import annotations

import html
import re
from html.parser import HTMLParser


class TableExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[dict] = []
        self._stack: list[str] = []
        self._current_table: dict | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._current_tag: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        self._stack.append(tag)
        if tag == "table":
            self._current_table = {"attrs": attrs_dict, "rows": []}
            self.tables.append(self._current_table)
        elif tag == "tr" and self._current_table is not None:
            self._current_row = []
        elif tag in {"th", "td"} and self._current_row is not None:
            self._current_cell = []
            self._current_tag = tag

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"} and self._current_row is not None and self._current_cell is not None:
            text = _clean_text("".join(self._current_cell))
            self._current_row.append(text)
            self._current_cell = None
            self._current_tag = None
        elif tag == "tr" and self._current_table is not None and self._current_row is not None:
            if any(cell for cell in self._current_row):
                self._current_table["rows"].append(self._current_row)
            self._current_row = None
        elif tag == "table":
            self._current_table = None
        if self._stack:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)


def extract_tables(page: str) -> list[dict]:
    parser = TableExtractor()
    parser.feed(page)
    return parser.tables


def strip_tags(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return _clean_text(value)


def find_input_value(page: str, name: str) -> str | None:
    pattern = rf'name="{re.escape(name)}"[^>]*value="([^"]*)"'
    match = re.search(pattern, page, re.IGNORECASE)
    return html.unescape(match.group(1)) if match else None


def page_contains_login_error(page: str) -> bool:
    lowered = page.lower()
    needles = [
        "felaktigt användarnamn eller lösenord",
        "wrong username or password",
    ]
    return any(needle in lowered for needle in needles)


def koha_page_looks_logged_in(page: str) -> bool:
    lowered = page.lower()
    return (
        'id="userdetails"' in lowered
        or 'logout.x=1' in lowered
        or 'din översikt' in lowered
        or 'your summary' in lowered
    )


def _clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()
