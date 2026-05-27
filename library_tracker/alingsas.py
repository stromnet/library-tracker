from __future__ import annotations

import logging
import re

from .debug_dump import dump_html
from .html_utils import (
    find_input_value,
    koha_page_looks_logged_in,
    page_contains_login_error,
    strip_tags,
)
from .http import Session
from .koha import KohaLibraryClient
from .models import AccountCredentials, LibraryAccountSnapshot
from .pagination import fetch_paginated_pages


class AlingsasLibrary(KohaLibraryClient):
    logger = logging.getLogger(__name__ + ".AlingsasLibrary")
    name = "alingsas"
    base_url = "https://kohaopac.alingsas.se"
    login_url = base_url + "/cgi-bin/koha/opac-user.pl"

    def __init__(self) -> None:
        self._session = Session()

    def fetch_account(self, credentials: AccountCredentials) -> LibraryAccountSnapshot:
        from .logging_utils import timed

        account_label = f"alingsas_{credentials.username}"

        with timed(self.logger, "alingsås login page"):
            login_page = self._session.get(self.login_url)
            csrf_token = find_input_value(login_page.body, "csrf_token") or ""
        with timed(self.logger, "alingsås login submit"):
            response = self._session.post_form(
                self.login_url,
                {
                    "koha_login_context": "opac",
                    "login_userid": credentials.username,
                    "login_password": credentials.password,
                    "login_op": "cud-login",
                    "csrf_token": csrf_token,
                },
                referer=self.login_url,
            )

        if page_contains_login_error(response.body) or not koha_page_looks_logged_in(response.body):
            dump_path = dump_html(account_label, "login_failure", response.body)
            raise ValueError(f"Alingsås login failed (debug: {dump_path})")

        with timed(self.logger, "alingsås parse account"):
            pages = fetch_paginated_pages(
                self._session, response.url, response.body, referer=self.login_url
            )
            snapshot = LibraryAccountSnapshot(
                library="Alingsås",
                account_name=self._extract_account_name(response.body),
                card_number=self._extract_card_number(response.body),
            )
            for idx, page in enumerate(pages, start=1):
                dump_path = dump_html(account_label, f"account_page_{idx}", page)
                snapshot.debug_files.append(str(dump_path))
                before_loans = len(snapshot.loans)
                before_res = len(snapshot.reservations)
                snapshot = self._extract_loans_and_reservations(page, snapshot=snapshot)
                self._attach_source_urls(snapshot.loans[before_loans:], page, "checkoutst")
                self._attach_source_urls(snapshot.reservations[before_res:], page, "holdst")
        for reservation in snapshot.reservations:
            if reservation.pickup_location:
                reservation.pickup_location = self._clean_pickup_location(
                    reservation.pickup_location
                )
        return snapshot

    def _extract_account_name(self, page: str) -> str | None:
        match = re.search(
            r'<div id="userdetails".*?<p[^>]*>\s*Hej,\s*([^<]+?)\s*<br',
            page,
            re.IGNORECASE | re.DOTALL,
        )
        return strip_tags(match.group(1)) if match else None

    def _extract_card_number(self, page: str) -> str | None:
        match = re.search(r'data-borrowernumber="(\d+)"', page, re.IGNORECASE)
        return strip_tags(match.group(1)) if match else None

    def _clean_pickup_location(self, value: str) -> str:
        return value.split(" Ändra ", 1)[0].strip()

    def _attach_source_urls(self, items: list, page: str, table_id: str) -> None:
        match = re.search(rf'<table[^>]+id="{table_id}".*?<tbody>(.*?)</tbody>', page, re.IGNORECASE | re.DOTALL)
        if not match:
            return
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', match.group(1), re.IGNORECASE | re.DOTALL)
        for item, row in zip(items, rows):
            link = re.search(r'<td class="title">.*?<a href="([^"]+)" class="title">', row, re.IGNORECASE | re.DOTALL)
            if link:
                item.raw["source_url"] = self.base_url + link.group(1)
