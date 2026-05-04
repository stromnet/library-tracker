from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AccountCredentials, LibraryAccountSnapshot


class LibraryClient(ABC):
    name: str

    @abstractmethod
    def fetch_account(self, credentials: AccountCredentials) -> LibraryAccountSnapshot:
        raise NotImplementedError
