"""scroll — Scroll in a direction."""

import json

import click

from modules import mouse_control


@click.command("scroll")
@click.argument("direction")
@click.argument("lines", type=int, default=3)
@click.option("--json", "as_json", is_flag=True, help="Output JSON")
def scroll_cmd(direction, lines, as_json):
    """Scroll in a direction by N lines."""
    mouse_control.scroll(direction, lines)

    if as_json:
        click.echo(json.dumps({
            "action": "scroll", "direction": direction,
            "lines": lines, "ok": True,
        }))
    else:
        click.echo(f"Scrolled {direction} {lines} lines")
