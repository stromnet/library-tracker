from __future__ import annotations

import html
from datetime import date, datetime, timedelta

from .models import LibraryAccountSnapshot
from .summary import DueHighlightItem, PickupHighlightItem, build_highlight_groups, parse_date


def render_html_report(
    snapshots: list[LibraryAccountSnapshot], errors: list[str] | None = None
) -> str:
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    groups = build_highlight_groups(snapshots)
    cards = "\n".join(_render_snapshot(snapshot) for snapshot in snapshots)
    error_html = ""
    if errors:
        items = "".join(f"<li>{html.escape(error)}</li>" for error in errors)
        error_html = f"<section><h2>Fel</h2><ul>{items}</ul></section>"
    highlights_html = ""
    if groups.overdue or groups.due_soon or groups.pickup_ready:
        sections: list[str] = []
        if groups.overdue:
            sections.append(_render_highlight_group("Försenade", groups.overdue))
        if groups.due_soon:
            sections.append(_render_highlight_group("Förfaller snart", groups.due_soon))
        if groups.pickup_ready:
            sections.append(_render_highlight_group("Klara att hämta", groups.pickup_ready))
        highlights_html = f"<section><h2>Höjdpunkter</h2>{''.join(sections)}</section>"

    return f"""<!DOCTYPE html>
<html lang=\"sv\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Biblioteksöversikt</title>
  <style>
    :root {{
      --bg: #f3f6fb;
      --panel: #ffffff;
      --panel-2: #f8faff;
      --text: #1f2937;
      --muted: #667085;
      --border: #dde3ee;
      --accent: #3457d5;
      --accent-soft: #e9efff;
      --warn: #c62828;
      --warn-soft: #fdecec;
      --shadow: 0 8px 24px rgba(30, 41, 59, 0.08);
    }}
    body {{ font-family: Inter, system-ui, sans-serif; margin: 0; background: linear-gradient(180deg, #eef3fb 0%, var(--bg) 100%); color: var(--text); }}
    header {{ background: linear-gradient(135deg, #22314d 0%, #3457d5 100%); color: white; padding: 28px 24px; box-shadow: var(--shadow); }}
    header h1 {{ margin: 0 0 6px; font-size: 30px; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    section {{ background: var(--panel); border: 1px solid var(--border); border-radius: 16px; padding: 20px; margin-bottom: 20px; box-shadow: var(--shadow); }}
    .grid {{ display: grid; grid-template-columns: 1fr; gap: 20px; }}
    .meta {{ color: var(--muted); font-size: 14px; line-height: 1.5; }}
    h1, h2, h3 {{ margin-top: 0; }}
    h2 {{ font-size: 22px; margin-bottom: 10px; }}
    h3 {{ font-size: 16px; margin: 18px 0 10px; color: #30415d; }}
    ul {{ padding-left: 20px; }}
    li {{ margin: 8px 0; }}
    .pill {{ display: inline-block; padding: 3px 10px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); font-size: 12px; margin-left: 8px; font-weight: 600; vertical-align: middle; }}
    .empty {{ color: var(--muted); font-style: italic; }}
    .subhead {{ margin-top: 18px; margin-bottom: 10px; font-size: 13px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); font-weight: 700; }}
    .highlight-group {{ margin-top: 16px; }}
    .highlight-table, .item-table {{ width: 100%; border-collapse: collapse; overflow: hidden; border-radius: 12px; }}
    .highlight-table th, .highlight-table td, .item-table th, .item-table td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); vertical-align: top; }}
    .highlight-table thead th, .item-table thead th {{ background: var(--panel-2); color: #30415d; font-size: 13px; text-transform: uppercase; letter-spacing: .05em; }}
    .highlight-table tbody tr:last-child td, .item-table tbody tr:last-child td {{ border-bottom: none; }}
    .date-urgent {{ color: var(--warn); font-weight: 700; }}
    .date-warning {{ color: #c77700; font-weight: 700; }}
    .status {{ color: #30415d; font-weight: 600; }}
    .card-head {{ margin-bottom: 10px; }}
    a {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <header>
    <h1>Biblioteksöversikt</h1>
    <div class=\"meta\">Genererad {generated_at}</div>
  </header>
  <main>
    {highlights_html}
    {error_html}
    <div class=\"grid\">{cards}</div>
  </main>
</body>
</html>
"""


def _render_snapshot(snapshot: LibraryAccountSnapshot) -> str:
    title = html.escape(snapshot.library + (f" / {snapshot.holder_alias}" if snapshot.holder_alias else ""))
    library = html.escape(snapshot.library)
    account_name = html.escape(snapshot.account_name) if snapshot.account_name else ""
    card_number = html.escape(snapshot.card_number) if snapshot.card_number and not snapshot.holder_alias else ""
    loans = _render_loans(snapshot)
    reservations = _render_reservations(snapshot)
    return f"""
<section>
  <div class=\"card-head\">
    <h2>{title}<span class=\"pill\">{library}</span></h2>
    <div class=\"meta\">{('Konto: ' + account_name + '<br>') if account_name else ''}{('Kortnummer: ' + card_number) if card_number else ''}</div>
  </div>
  <div class=\"subhead\">Lån</div>
  {loans}
  <div class=\"subhead\">Reservationer</div>
  {reservations}
</section>
"""


def _render_loans(snapshot: LibraryAccountSnapshot) -> str:
    if not snapshot.loans:
        return '<div class="empty">Inga lån hittades</div>'
    rows = []
    for loan in snapshot.loans:
        rows.append(
            "<tr>"
            f"<td>{_render_title_link(loan.title, loan.raw.get('source_url'))}</td>"
            f"<td>{html.escape(loan.author or '')}</td>"
            f"<td>{html.escape(loan.branch or '')}</td>"
            f"<td>{_format_date_cell(loan.due_date)}</td>"
            f"<td class=\"status\">{html.escape(loan.status or '')}</td>"
            "</tr>"
        )
    return (
        '<table class="item-table"><thead><tr>'
        '<th>Titel</th><th>Författare</th><th>Bibliotek</th><th>Förfallo</th><th>Status</th>'
        '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'
    )


def _render_reservations(snapshot: LibraryAccountSnapshot) -> str:
    if not snapshot.reservations:
        return '<div class="empty">Inga reservationer hittades</div>'
    rows = []
    for reservation in snapshot.reservations:
        rows.append(
            "<tr>"
            f"<td>{_render_title_link(reservation.title, reservation.raw.get('source_url'))}</td>"
            f"<td>{html.escape(reservation.pickup_location or '')}</td>"
            f"<td>{html.escape(reservation.queue_position or '')}</td>"
            f"<td>{_format_date_cell(reservation.expires_at)}</td>"
            f"<td class=\"status\">{html.escape(reservation.status or '')}</td>"
            "</tr>"
        )
    return (
        '<table class="item-table"><thead><tr>'
        '<th>Titel</th><th>Hämtställe</th><th>Köplats</th><th>Förfaller</th><th>Status</th>'
        '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'
    )


def _render_highlight_group(title: str, items: list[DueHighlightItem] | list[PickupHighlightItem]) -> str:
    rows = []
    is_pickup = title.lower() == 'klara att hämta'
    for item in items:
        if is_pickup:
            item = item  # type: ignore[assignment]
            rows.append(
                "<tr>"
                f"<td>{html.escape(item.item)}</td>"
                f"<td>{html.escape(item.library)}</td>"
                f"<td>{html.escape(item.pickup or '')}</td>"
                f"<td>{html.escape(item.queue or '')}</td>"
                f"<td>{_format_date_cell(item.expires)}</td>"
                f"<td class=\"status\">{html.escape(item.status or '')}</td>"
                "</tr>"
            )
        else:
            item = item  # type: ignore[assignment]
            rows.append(
                "<tr>"
                f"<td>{html.escape(item.item)}</td>"
                f"<td>{html.escape(item.library)}</td>"
                f"<td>{_format_date_cell(item.due_date)}</td>"
                "</tr>"
            )
    header = (
        '<th>Titel</th><th>Bibliotek</th><th>Hämtställe</th><th>Köplats</th><th>Förfaller</th><th>Status</th>'
        if is_pickup
        else '<th>Titel</th><th>Bibliotek</th><th>Datum</th>'
    )
    return (
        f'<div class="highlight-group"><h3>{html.escape(title)}</h3>'
        f'<table class="highlight-table"><thead><tr>{header}</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'
    )


def _format_date_cell(value: str | None) -> str:
    if not value:
        return ''
    parsed = parse_date(value)
    escaped = html.escape(value)
    if parsed:
        delta = (parsed - date.today()).days
        if delta <= 5:
            return f'<span class="date-urgent">{escaped}</span>'
        if delta <= 10:
            return f'<span class="date-warning">{escaped}</span>'
    return escaped


def _render_title_link(title: str, url: str | None) -> str:
    escaped_title = html.escape(title)
    if url:
        return f'<a href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">{escaped_title}</a>'
    return escaped_title
