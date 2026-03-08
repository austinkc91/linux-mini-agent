"""Capture pane content."""
import click

from modules import tmux
from modules.errors import DriveError
from modules.output import emit, emit_error


@click.command()
@click.argument("session")
@click.option("--pane", default=None, help="Target pane index.")
@click.option("--lines", default=None, type=int, help="Scrollback lines to capture.")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
def logs(session: str, pane: str | None, lines: int | None, as_json: bool):
    """Capture the current pane output from a tmux session."""
    try:
        start_line = -abs(lines) if lines else None
        content = tmux.capture_pane(session, pane=pane, start_line=start_line)
        emit(
            {"ok": True, "session": session, "content": content},
            json=as_json,
            human_lines=content,
        )
    except DriveError as e:
        emit_error(e, json=as_json)
