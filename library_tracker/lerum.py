from __future__ import annotations

import html
import logging
import re

from .base import LibraryClient
from .debug_dump import dump_html
from .html_utils import find_input_value, strip_tags
from .http import Session
from .models import AccountCredentials, LibraryAccountSnapshot, Loan, Reservation
from .pagination import fetch_paginated_pages


class LerumLibrary(LibraryClient):
    logger = logging.getLogger(__name__ + ".LerumLibrary")
    name = "lerum"
    base_url = "https://bibliotek.lerum.se"
    login_url = base_url + "/vufind/MyResearch/UserLogin"
    account_url = base_url + "/vufind/MyResearch/Home"

    def __init__(self) -> None:
        self._session = Session()

    def fetch_account(self, credentials: AccountCredentials) -> LibraryAccountSnapshot:
        from .logging_utils import timed

        account_label = f"lerum_{credentials.username}"

        with timed(self.logger, "lerum login page"):
            login_page = self._session.get(self.login_url)
            csrf = find_input_value(login_page.body, "csrf") or ""
        with timed(self.logger, "lerum login submit"):
            response = self._session.post_form(
                self.account_url,
                {
                    "username": credentials.username,
                    "password": credentials.password,
                    "auth_method": "ILS",
                    "csrf": csrf,
                    "processLogin": "Logga in",
                },
                referer=self.login_url,
            )

        if self._is_login_failure(response.body):
            raise ValueError("Lerum login failed")

        with timed(self.logger, "lerum fetch account pages"):
            checked_out_page = self._session.get(
                self.base_url + "/vufind/MyResearch/CheckedOut", referer=self.account_url
            )
            holds_page = self._session.get(
                self.base_url + "/vufind/MyResearch/Holds", referer=self.account_url
            )
            checked_out_pages = fetch_paginated_pages(
                self._session,
                self.base_url + "/vufind/MyResearch/CheckedOut",
                checked_out_page.body,
                referer=self.account_url,
            )
            holds_pages = fetch_paginated_pages(
                self._session,
                self.base_url + "/vufind/MyResearch/Holds",
                holds_page.body,
                referer=self.account_url,
            )

        with timed(self.logger, "lerum parse account"):
            snapshot = LibraryAccountSnapshot(
                library="Lerum",
                account_name=self._extract_account_name(response.body),
                card_number=credentials.username,
            )
            for idx, page in enumerate(checked_out_pages, start=1):
                dump_path = dump_html(account_label, f"checked_out_{idx}", page)
                snapshot.debug_files.append(str(dump_path))
                snapshot.loans.extend(self._extract_loans(page))
            for idx, page in enumerate(holds_pages, start=1):
                dump_path = dump_html(account_label, f"holds_{idx}", page)
                snapshot.debug_files.append(str(dump_path))
                snapshot.reservations.extend(self._extract_holds(page))
        return snapshot

    def _is_login_failure(self, page: str) -> bool:
        lowered = page.lower()
        return (
            "användarnamn/lösenord stämmer inte" in lowered
            or 'name="loginform"' in lowered
        )

    def _extract_account_name(self, page: str) -> str | None:
        patterns = [
            r"Hej,\s*([^<]+)",
            r"Welcome,\s*([^<]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, page, re.IGNORECASE)
            if match:
                return strip_tags(match.group(1))
        return None

    def _extract_card_number(self, page: str) -> str | None:
        match = re.search(r"Lånekortnummer[^\d]*(\d+)", page, re.IGNORECASE)
        return strip_tags(match.group(1)) if match else None

    def _extract_loans(self, page: str) -> list[Loan]:
        results: list[Loan] = []
        for item in re.findall(r'<li[^>]+class="result".*?</li>', page, re.IGNORECASE | re.DOTALL):
            title = self._match(item, r'class="title">(.*?)</a>')
            if not title:
                continue
            link = self._match(item, r'<a href="([^"]+)" class="title">')
            author = self._match(item, r'av:\s*<a[^>]*>(.*?)</a>')
            branch = self._match(item, r'Utlåningsställe:</strong>\s*(.*?)\s*<br')
            due_date = self._match(item, r'Förfallodag:\s*([^<]+)')
            status = self._match(item, r'<div class="alert alert-info">(.*?)</div>')
            raw = {}
            if link:
                raw['source_url'] = self.base_url + html.unescape(link).replace('&#x2F;', '/') if not link.startswith('http') else html.unescape(link)
            results.append(
                Loan(
                    title=strip_tags(title),
                    author=strip_tags(author) if author else None,
                    branch=strip_tags(branch) if branch else None,
                    due_date=strip_tags(due_date) if due_date else None,
                    status=strip_tags(status) if status else None,
                    raw=raw,
                )
            )
        return results

    def _extract_holds(self, page: str) -> list[Reservation]:
        results: list[Reservation] = []
        for item in re.findall(r'<li[^>]+class="result".*?</li>', page, re.IGNORECASE | re.DOTALL):
            title = self._match(item, r'class="title">(.*?)</a>')
            if not title:
                continue
            link = self._match(item, r'<a href="([^"]+)" class="title">')
            author = self._match(item, r'av:\s*<a[^>]*>(.*?)</a>')
            pickup = self._match(item, r'Avhämtningsställe:</strong>\s*(.*?)\s*<br')
            created = self._match(item, r'Skapad:</strong>\s*([^<|]+)')
            expires = self._match(item, r'Förfaller:</strong>\s*([^<]+)')
            queue = self._match(item, r'Placering i kön:</strong>\s*([^<]+)')
            if 'Kan avhämtas' in item:
                status = 'Kan avhämtas'
            elif 'På väg' in item:
                status = 'På väg'
            else:
                status = self._match(item, r'<p>\s*<strong>\s*([^<]+)\s*</strong>\s*</p>')
                if not status and queue:
                    status = 'Aktiv'
            results.append(
                Reservation(
                    title=strip_tags(title),
                    author=strip_tags(author) if author else None,
                    pickup_location=strip_tags(pickup) if pickup else None,
                    expires_at=strip_tags(expires) if expires else None,
                    queue_position=strip_tags(queue) if queue else None,
                    status=strip_tags(status) if status else None,
                    raw=(
                        {
                            **({"created": strip_tags(created)} if created else {}),
                            **({"source_url": self.base_url + html.unescape(link).replace('&#x2F;', '/')} if link and not link.startswith('http') else ({"source_url": html.unescape(link)} if link else {})),
                        }
                    ),
                )
            )
        return results

    def _match(self, text: str, pattern: str) -> str | None:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return match.group(1) if match else None
