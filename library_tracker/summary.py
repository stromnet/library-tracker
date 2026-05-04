from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .models import LibraryAccountSnapshot, Loan, Reservation


@dataclass(slots=True)
class DueHighlightItem:
    label: str
    library: str
    item: str
    due_date: str
    sort_date: date | None
    loan: Loan
    snapshot: LibraryAccountSnapshot


@dataclass(slots=True)
class PickupHighlightItem:
    label: str
    library: str
    item: str
    pickup: str | None
    queue: str | None
    expires: str | None
    status: str | None
    sort_date: date | None
    reservation: Reservation
    snapshot: LibraryAccountSnapshot


@dataclass(slots=True)
class HighlightGroups:
    overdue: list[DueHighlightItem]
    due_soon: list[DueHighlightItem]
    pickup_ready: list[PickupHighlightItem]


def build_highlight_groups(snapshots: list[LibraryAccountSnapshot]) -> HighlightGroups:
    today = date.today()
    soon_limit = today + timedelta(days=14)
    overdue: list[DueHighlightItem] = []
    due_soon: list[DueHighlightItem] = []
    pickup_ready: list[PickupHighlightItem] = []

    for snapshot in snapshots:
        name = snapshot.library + (f" / {snapshot.holder_alias}" if snapshot.holder_alias else "")
        for loan in snapshot.loans:
            due = parse_date(loan.due_date)
            if not due:
                continue
            item = DueHighlightItem(
                label="Due",
                library=name,
                item=loan.title,
                due_date=due.isoformat(),
                sort_date=due,
                loan=loan,
                snapshot=snapshot,
            )
            if due < today:
                overdue.append(item)
            elif due <= soon_limit:
                due_soon.append(item)

        for reservation in snapshot.reservations:
            if not _is_pickup_ready(reservation):
                continue
            pickup_ready.append(
                PickupHighlightItem(
                    label="Pickup",
                    library=name,
                    item=reservation.title,
                    pickup=reservation.pickup_location,
                    queue=reservation.queue_position,
                    expires=reservation.expires_at,
                    status=reservation.status,
                    sort_date=parse_date(reservation.expires_at),
                    reservation=reservation,
                    snapshot=snapshot,
                )
            )

    return HighlightGroups(
        overdue=_sort_items(overdue),
        due_soon=_sort_items(due_soon),
        pickup_ready=_sort_items(pickup_ready),
    )


def build_highlights(snapshots: list[LibraryAccountSnapshot]) -> list[str]:
    groups = build_highlight_groups(snapshots)
    lines: list[str] = []
    lines.extend(build_highlights_from_group(groups.overdue))
    lines.extend(build_highlights_from_group(groups.due_soon))
    lines.extend(build_highlights_from_group(groups.pickup_ready))
    return lines


def build_highlights_from_group(items: list[DueHighlightItem] | list[PickupHighlightItem]) -> list[str]:
    lines: list[str] = []
    for item in items:
        if isinstance(item, DueHighlightItem):
            lines.append(_format_due_highlight(item))
        else:
            lines.append(_format_pickup_highlight(item))
    return lines


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned in {"-", "Upphör aldrig"}:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            pass
    return None


def _is_pickup_ready(reservation: Reservation) -> bool:
    status = (reservation.status or "").lower()
    return any(text in status for text in ["kan avhämtas", "väntar", "under transport"])


def _format_due_highlight(item: DueHighlightItem) -> str:
    return f"DUE {item.due_date}: {item.item} ({item.library})"


def _format_pickup_highlight(item: PickupHighlightItem) -> str:
    pickup = f" @ {item.pickup}" if item.pickup else ""
    queue = f" (queue {item.queue})" if item.queue else ""
    expires = f" (expires {item.expires})" if item.expires and item.expires not in {'-', 'Upphör aldrig'} else ""
    return f"READY {item.library}: {item.item}{pickup}{queue}{expires} [{item.status}]"


def _sort_items(items: list[object]) -> list[object]:
    return sorted(
        items,
        key=lambda item: (
            getattr(item, 'sort_date', None) is None,
            getattr(item, 'sort_date', None) or date.max,
            getattr(item, 'item', '').lower(),
            getattr(item, 'library', '').lower(),
        ),
    )
