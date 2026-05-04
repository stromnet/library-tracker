from __future__ import annotations

import html
import logging
import re
import urllib.parse

from .base import LibraryClient
from .html_utils import strip_tags
from .http import Session
from .models import AccountCredentials, LibraryAccountSnapshot, Loan, Reservation
from .pagination import extract_wicket_component_html, extract_wicket_next_url


class MolnlyckeLibrary(LibraryClient):
    logger = logging.getLogger(__name__ + ".MolnlyckeLibrary")
    name = "molnlycke"
    base_url = "https://bibliotek.harryda.se"
    portal_login_url = base_url + "/c/portal/login?p_l_id=403082"
    overview_url = base_url + "/protected/my-account/overview"

    def __init__(self) -> None:
        self._session = Session()

    def fetch_account(self, credentials: AccountCredentials) -> LibraryAccountSnapshot:
        from .logging_utils import timed

        with timed(self.logger, "mölnlycke portal login"):
            self._login_portal(credentials)
        with timed(self.logger, "mölnlycke patron login"):
            overview_page = self._session.get(self.overview_url)
            self._login_patron(credentials, overview_page.body)
            overview_page = self._session.get(self.overview_url)
        with timed(self.logger, "mölnlycke fetch portlets"):
            loans_pages = self._render_portlet_pages(
                overview_page.body, "loansWicket_WAR_arenaportlet", "loansWicket"
            )
            reservations_pages = self._render_portlet_pages(
                overview_page.body,
                "reservationsWicket_WAR_arenaportlet",
                "reservationsWicket",
            )

        with timed(self.logger, "mölnlycke parse account"):
            snapshot = LibraryAccountSnapshot(
                library="Mölnlycke",
                account_name=self._extract_account_name(overview_page.body),
                card_number=credentials.username,
            )
            for page in loans_pages:
                snapshot.loans.extend(self._extract_loans(page))
            for page in reservations_pages:
                snapshot.reservations.extend(self._extract_reservations(page))
        return snapshot

    def _login_portal(self, credentials: AccountCredentials) -> None:
        page = self._session.get(self.portal_login_url)
        action, fields = self._extract_form(
            page.body, r'<form[^>]*action="([^"]*LoginPortlet[^"]*)"[^>]*method="post"[^>]*>(.*?)</form>'
        )
        fields["_com_liferay_login_web_portlet_LoginPortlet_login"] = credentials.username
        fields["_com_liferay_login_web_portlet_LoginPortlet_password"] = credentials.password
        self._session.post_form(action, fields, referer=self.portal_login_url)

    def _login_patron(self, credentials: AccountCredentials, overview_page: str) -> None:
        url = self._portlet_refresh_url(overview_page, "patronLogin_WAR_arenaportlet")
        portlet = self._session.get(url, referer=self.overview_url)
        action, fields = self._extract_form(
            portlet.body, r'<form[^>]+method="post" action="([^"]+)"[^>]*>(.*?)</form>'
        )
        fields["openTextUsernameContainer:openTextUsername"] = credentials.username
        fields["textPassword"] = credentials.password
        self._session.post_form(action, fields, referer=self.overview_url)

    def _render_portlet(self, overview_page: str, portlet_id: str) -> str:
        url = self._portlet_refresh_url(overview_page, portlet_id)
        return self._session.get(url, referer=self.overview_url).body

    def _render_portlet_pages(
        self, overview_page: str, portlet_id: str, component_hint: str, max_pages: int = 10
    ) -> list[str]:
        pages = [self._render_portlet(overview_page, portlet_id)]
        current = pages[0]
        for _ in range(max_pages - 1):
            next_url = extract_wicket_next_url(current)
            if not next_url:
                break
            response = self._session.get(next_url, referer=self.overview_url).body
            next_page = extract_wicket_component_html(response, component_hint)
            if not next_page or next_page == current:
                break
            pages.append(next_page)
            current = next_page
        return pages

    def _portlet_refresh_url(self, page: str, portlet_id: str) -> str:
        match = re.search(portlet_id + r'.*?refreshURL:"([^"]+)"', page, re.IGNORECASE)
        if not match:
            raise ValueError(f"Could not find refresh URL for {portlet_id}")
        raw = match.group(1).replace('\\x3d', '=').replace('\\x26', '&')
        return self.base_url + raw

    def _extract_form(self, page: str, pattern: str) -> tuple[str, dict[str, str]]:
        form = re.search(pattern, page, re.IGNORECASE | re.DOTALL)
        if not form:
            raise ValueError("Expected form not found")
        action = html.unescape(form.group(1))
        body = form.group(2)
        fields: dict[str, str] = {}
        for match in re.finditer(r'<input[^>]+name="([^"]+)"[^>]*?(?:value="([^"]*)")?[^>]*>', body, re.IGNORECASE):
            name = html.unescape(match.group(1))
            value = html.unescape(match.group(2) or "")
            if name not in {
                "_com_liferay_login_web_portlet_LoginPortlet_login",
                "_com_liferay_login_web_portlet_LoginPortlet_password",
                "openTextUsernameContainer:openTextUsername",
                "textPassword",
            }:
                fields[name] = value
        return action, fields

    def _extract_account_name(self, page: str) -> str | None:
        match = re.search(r'data-qa-id="user-name"[^>]*>(.*?)<', page, re.IGNORECASE)
        return strip_tags(match.group(1)) if match else None

    def _extract_loans(self, page: str) -> list[Loan]:
        results: list[Loan] = []
        for row in re.findall(r'<tr class="arena-renewal-[^"]*".*?</tr>', page, re.IGNORECASE | re.DOTALL):
            title = self._match(row, r'<div class="arena-record-title">.*?<span>(.*?)</span>')
            if not title:
                continue
            author = self._match(row, r'<div class="arena-record-author">.*?<span class="arena-value">(.*?)</span>')
            branch = self._match(row, r'Lånad på:\s*</span>\s*<span class="arena-value">(.*?)</span>')
            due_date = self._match(row, r'arena-renewal-date-value[^>]*>(.*?)</span>')
            alert = self._match(row, r'<span class="arena-alert">(.*?)</span>')
            message = self._match(row, r'<span class="arena-loan-status-message">(.*?)</span>')
            status = " - ".join(part for part in [strip_tags(alert) if alert else None, strip_tags(message) if message else None] if part)
            link = self._match(row, r'<div class="arena-record-title">\s*<a href="([^"]+)"')
            raw = {"source_url": html.unescape(link)} if link else {}
            results.append(
                Loan(
                    title=strip_tags(title),
                    author=strip_tags(author) if author else None,
                    branch=strip_tags(branch).rsplit(" ", 1)[0] if branch else None,
                    due_date=strip_tags(due_date) if due_date else None,
                    status=status or None,
                    raw=raw,
                )
            )
        return results

    def _extract_reservations(self, page: str) -> list[Reservation]:
        results: list[Reservation] = []
        details_blocks = re.findall(
            r'<table class="arena-reservation-details">.*?</table>',
            page,
            re.IGNORECASE | re.DOTALL,
        )
        title_blocks = re.findall(
            r'<div class="arena-record-title">.*?</div>',
            page,
            re.IGNORECASE | re.DOTALL,
        )
        author_blocks = re.findall(
            r'<div class="arena-record-author">.*?</div>',
            page,
            re.IGNORECASE | re.DOTALL,
        )
        for index, details in enumerate(details_blocks):
            title = self._match(title_blocks[index] if index < len(title_blocks) else "", r'<span>(.*?)</span>')
            author = self._match(author_blocks[index] if index < len(author_blocks) else "", r'<span class="arena-value">(.*?)</span>')
            pickup = self._match(details, r'Hämtställe:</span>\s*<span class="arena-value">(.*?)</span>')
            queue = self._match(details, r'Köplats:</span>\s*<span class="arena-value">(.*?)</span>')
            created = self._match(details, r'Skapad:</span>\s*<span class="arena-value">(.*?)</span>')
            valid_to = self._match(details, r'Giltig till:</span>\s*<span class="arena-value">(.*?)</span>')
            status = self._match(details, r'Status</span>\s*<span class="arena-value">(.*?)</span>')
            if title:
                link = self._match(title_blocks[index] if index < len(title_blocks) else "", r'<a href="([^"]+)"')
                raw = ({"created": strip_tags(created)} if created else {})
                if link:
                    raw["source_url"] = html.unescape(link)
                results.append(
                    Reservation(
                        title=strip_tags(title),
                        author=strip_tags(author) if author else None,
                        pickup_location=strip_tags(pickup) if pickup else None,
                        queue_position=strip_tags(queue) if queue else None,
                        expires_at=strip_tags(valid_to) if valid_to else None,
                        status=strip_tags(status) if status else None,
                        raw=raw,
                    )
                )
        return results

    def _match(self, text: str, pattern: str) -> str | None:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return match.group(1) if match else None
