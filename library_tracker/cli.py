from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

import yaml

from .alingsas import AlingsasLibrary
from .html_output import render_html_report
from .lerum import LerumLibrary
from .logging_utils import configure_logging, timed
from .models import AccountCredentials, LibraryAccountSnapshot
from .molnlycke import MolnlyckeLibrary
from .partille import PartilleLibrary
from .summary import build_highlight_groups, build_highlights_from_group


def build_client(library_name: str):
    normalized = library_name.strip().lower()
    if normalized == "partille":
        return PartilleLibrary()
    if normalized in {"alingsas", "alingsås"}:
        return AlingsasLibrary()
    if normalized == "lerum":
        return LerumLibrary()
    if normalized in {"molnlycke", "mölnlycke", "harryda", "härryda"}:
        return MolnlyckeLibrary()
    raise SystemExit(f"Unsupported library: {library_name}")


def snapshot_to_dict(snapshot: LibraryAccountSnapshot) -> dict:
    return {
        "library": snapshot.library,
        "holder_alias": snapshot.holder_alias,
        "account_name": snapshot.account_name,
        "card_number": snapshot.card_number,
        "loans": [asdict(loan) for loan in snapshot.loans],
        "reservations": [asdict(reservation) for reservation in snapshot.reservations],
        "notes": snapshot.notes,
    }


def load_config(path: str) -> list[dict]:
    data = yaml.safe_load(Path(path).read_text())
    accounts = data.get("accounts", []) if isinstance(data, dict) else []
    if not isinstance(accounts, list):
        raise ValueError("Konfigurationsfilen måste innehålla en 'accounts'-lista")
    normalized: list[dict] = []
    for account in accounts:
        if isinstance(account, dict) and "holder_alias" not in account and "label" in account:
            label = str(account["label"])
            library = str(account.get("library", ""))
            alias = label
            prefix = library + " / "
            if label.lower().startswith(prefix.lower()):
                alias = label[len(prefix):]
            account = {**account, "holder_alias": alias}
        normalized.append(account)
    return normalized


def print_snapshot(snapshot: LibraryAccountSnapshot) -> None:
    title = snapshot.library + (f" / {snapshot.holder_alias}" if snapshot.holder_alias else "")
    print(f"Bibliotek: {title}")
    if snapshot.account_name:
        print(f"Konto: {snapshot.account_name}")
    if snapshot.card_number and not snapshot.holder_alias:
        print(f"Kortnummer: {snapshot.card_number}")

    print("Lån:")
    if snapshot.loans:
        for loan in snapshot.loans:
            due = f" (förfaller {loan.due_date})" if loan.due_date else ""
            status = f" [{loan.status}]" if loan.status else ""
            print(f"- {loan.title}{due}{status}")
    else:
        print("- inga hittades")

    print("Reservationer:")
    if snapshot.reservations:
        for reservation in snapshot.reservations:
            parts = [f"- {reservation.title}"]
            if reservation.status:
                parts.append(f"[{reservation.status}]")
            if reservation.pickup_location:
                parts.append(f"@ {reservation.pickup_location}")
            if reservation.queue_position:
                parts.append(f"(köplats {reservation.queue_position})")
            if reservation.expires_at:
                parts.append(f"(förfaller {reservation.expires_at})")
            print(" ".join(parts))
    else:
        print("- inga hittades")

    if snapshot.notes:
        print("Anteckningar:")
        for note in snapshot.notes:
            print(f"- {note}")


def print_combined_summary(
    snapshots: list[LibraryAccountSnapshot], errors: list[str] | None = None
) -> None:
    print("Sammanfattning")
    print("==============")
    groups = build_highlight_groups(snapshots)
    if groups.overdue or groups.due_soon or groups.pickup_ready:
        print("Höjdpunkter")
        print("-----------")
        if groups.overdue:
            print("Försenade")
            for line in build_highlights_from_group(groups.overdue):
                print(f"- {line}")
        if groups.due_soon:
            print("Förfaller snart")
            for line in build_highlights_from_group(groups.due_soon):
                print(f"- {line}")
        if groups.pickup_ready:
            print("Klara att hämta")
            for line in build_highlights_from_group(groups.pickup_ready):
                print(f"- {line}")
        print()
    if errors:
        print("Fel")
        print("---")
        for error in errors:
            print(f"- {error}")
        print()
    for snapshot in snapshots:
        print()
        print_snapshot(snapshot)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Biblioteksöversikt")
    parser.add_argument("library", nargs="?", help="Biblioteks-id, t.ex. partille")
    parser.add_argument("username", nargs="?", help="Användarnamn / kortnummer")
    parser.add_argument("password", nargs="?", help="Lösenord / PIN")
    parser.add_argument("--config", help="YAML-fil med konton")
    parser.add_argument("--json", action="store_true", help="Skriv ut JSON")
    parser.add_argument("--html", help="Skriv en HTML-rapport till denna fil")
    parser.add_argument("--verbose", action="store_true", help="Aktivera loggning")
    args = parser.parse_args(argv)

    configure_logging(args.verbose)
    logger = logging.getLogger(__name__)
    snapshots: list[LibraryAccountSnapshot] = []
    errors: list[str] = []

    try:
        if args.config:
            accounts = load_config(args.config)

            def run_account(account: dict) -> LibraryAccountSnapshot:
                label = account.get("holder_alias") or account["library"]
                client = build_client(account["library"])
                credentials = AccountCredentials(
                    username=str(account["username"]),
                    password=str(account["password"]),
                )
                with timed(logger, f"fetch {label}"):
                    snapshot = client.fetch_account(credentials)
                    if account.get("holder_alias"):
                        snapshot.holder_alias = str(account["holder_alias"])
                    return snapshot

            with timed(logger, "fetch all configured accounts"):
                with ThreadPoolExecutor(max_workers=min(8, max(1, len(accounts)))) as executor:
                    future_map = {
                        executor.submit(run_account, account): account for account in accounts
                    }
                    for future in as_completed(future_map):
                        account = future_map[future]
                        label = account.get("holder_alias") or account["library"]
                        try:
                            snapshots.append(future.result())
                        except Exception as exc:  # noqa: BLE001
                            errors.append(f"{label}: {exc}")
                snapshots.sort(key=lambda snapshot: snapshot.library)
        else:
            if not (args.library and args.username and args.password):
                parser.error("library, username och password krävs om inte --config används")
            client = build_client(args.library)
            credentials = AccountCredentials(username=args.username, password=args.password)
            with timed(logger, f"fetch {args.library}"):
                snapshot = client.fetch_account(credentials)
                snapshots.append(snapshot)
    except Exception as exc:  # noqa: BLE001
        print(f"FEL: {exc}", file=sys.stderr)
        return 1

    if args.json:
        payload = {
            "snapshots": [snapshot_to_dict(snapshot) for snapshot in snapshots],
            "errors": errors,
        }
        if len(snapshots) == 1 and not errors:
            print(json.dumps(payload["snapshots"][0], ensure_ascii=False, indent=2))
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if snapshots else 1

    if args.html:
        Path(args.html).write_text(
            render_html_report(snapshots, errors=errors), encoding="utf-8"
        )
        print(f"Skrev HTML-rapport till {args.html}")
        return 0 if snapshots else 1

    if len(snapshots) == 1 and not errors:
        print_snapshot(snapshots[0])
    else:
        print_combined_summary(snapshots, errors=errors)

    return 0 if snapshots else 1


if __name__ == "__main__":
    raise SystemExit(main())
