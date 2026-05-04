from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class AccountCredentials:
    username: str
    password: str


@dataclass(slots=True)
class Loan:
    title: str
    due_date: Optional[str] = None
    status: Optional[str] = None
    author: Optional[str] = None
    branch: Optional[str] = None
    renewable: Optional[bool] = None
    raw: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class Reservation:
    title: str
    status: Optional[str] = None
    pickup_location: Optional[str] = None
    queue_position: Optional[str] = None
    expires_at: Optional[str] = None
    author: Optional[str] = None
    raw: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class LibraryAccountSnapshot:
    library: str
    holder_alias: Optional[str] = None
    account_name: Optional[str] = None
    card_number: Optional[str] = None
    loans: list[Loan] = field(default_factory=list)
    reservations: list[Reservation] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
