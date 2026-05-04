from __future__ import annotations

from abc import ABC

from .base import LibraryClient
from .html_utils import extract_tables
from .models import LibraryAccountSnapshot, Loan, Reservation


class KohaLibraryClient(LibraryClient, ABC):
    def _extract_loans_and_reservations(
        self, page: str, *, snapshot: LibraryAccountSnapshot
    ) -> LibraryAccountSnapshot:
        tables = extract_tables(page)
        for table in tables:
            rows = table["rows"]
            if len(rows) < 2:
                continue
            headers = [cell.lower() for cell in rows[0]]
            if any(
                "förfallo" in h or "due" in h or "återlämnas" in h or "utlånad" in h
                for h in headers
            ):
                snapshot.loans.extend(self._parse_loans(rows[0], rows[1:]))
            elif any("reservation" in h or "kö" in h or "pickup" in h for h in headers):
                snapshot.reservations.extend(self._parse_reservations(rows[0], rows[1:]))
        return snapshot

    def _parse_loans(self, headers: list[str], rows: list[list[str]]) -> list[Loan]:
        results: list[Loan] = []
        for row in rows:
            if not any(row):
                continue
            mapping = self._zip_row(headers, row)
            title = self._pick(mapping, "title", "titel", "material")
            if not title:
                continue
            results.append(
                Loan(
                    title=self._normalize_title(title),
                    due_date=self._pick(mapping, "due", "förfallo", "återlämnas"),
                    status=self._pick(mapping, "status"),
                    author=self._pick(mapping, "author", "författare"),
                    branch=self._pick(mapping, "library", "bibliotek", "branch"),
                    raw=mapping,
                )
            )
        return results

    def _parse_reservations(
        self, headers: list[str], rows: list[list[str]]) -> list[Reservation]:
        results: list[Reservation] = []
        for row in rows:
            if not any(row):
                continue
            mapping = self._zip_row(headers, row)
            title = self._pick(mapping, "title", "titel", "material")
            if not title:
                continue
            results.append(
                Reservation(
                    title=self._normalize_title(title),
                    status=self._pick(mapping, "status"),
                    pickup_location=self._pick(mapping, "pickup", "hämta", "bibliotek"),
                    queue_position=self._pick(mapping, "kö", "queue", "position"),
                    expires_at=self._pick(mapping, "expire", "utgår", "expires"),
                    author=self._pick(mapping, "author", "författare"),
                    raw=mapping,
                )
            )
        return results

    def _zip_row(self, headers: list[str], row: list[str]) -> dict[str, str]:
        width = min(len(headers), len(row))
        return {headers[i]: row[i] for i in range(width)}

    def _pick(self, mapping: dict[str, str], *needles: str) -> str | None:
        for key, value in mapping.items():
            lowered = key.lower()
            if any(needle in lowered for needle in needles):
                return value or None
        return None

    def _normalize_title(self, title: str) -> str:
        title = title.strip()
        if title.endswith(" /"):
            title = title[:-2].rstrip()
        return title
