"""find — Search elements by text in a snapshot."""

import json

import click

from modules import element_store
from modules.errors import SteerError


@click.command("find")
@click.argument("query")
@click.option("--snapshot", default=None, help="Snapshot ID to search in")
@click.option("--exact", is_flag=True, help="Exact match only")
@click.option("--json", "as_json", is_flag=True, help="Output JSON")
def find_cmd(query, snapshot, exact, as_json):
    """Search elements by text in the latest snapshot."""
    try:
        if snapshot:
            els = element_store.load(snapshot)
            if els is None:
                from modules.errors import NoSnapshot
                raise NoSnapshot()
            snap_id = snapshot
        else:
            result = element_store.latest()
            if result is None:
                from modules.errors import NoSnapshot
                raise NoSnapshot()
            snap_id, els = result

        lq = query.lower()
        if exact:
            matches = [e for e in els if
                       e.get("label", "").lower() == lq or
                       (e.get("value") or "").lower() == lq]
        else:
            matches = [e for e in els if
                       lq in e.get("label", "").lower() or
                       lq in (e.get("value") or "").lower()]

        if as_json:
            click.echo(json.dumps({
                "snapshot": snap_id,
                "query": query,
                "count": len(matches),
                "matches": matches,
            }))
        else:
            click.echo(f"snapshot: {snap_id}")
            click.echo(f'query: "{query}"')
            click.echo(f"matches: {len(matches)}")
            click.echo("")
            if not matches:
                click.echo("  (no matches)")
            else:
                for el in matches:
                    lbl = el.get("label", "") or el.get("value", "") or ""
                    t = lbl[:50]
                    eid = el.get("id", "?").ljust(6)
                    erole = el.get("role", "?").ljust(14)
                    click.echo(f'  {eid} {erole} "{t}"  ({el["x"]},{el["y"]} {el["width"]}x{el["height"]})')

    except SteerError as e:
        if as_json:
            click.echo(json.dumps({"error": str(e), "ok": False}))
        else:
            click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
