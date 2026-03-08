"""Session management: create, list, kill."""
import click

from modules import tmux
from modules.errors import DriveError
from modules.output import emit, emit_error


@click.group()
def session():
    """Manage tmux sessions."""
    pass


@session.command()
@click.argument("name")
@click.option("--window", default=None, help="Name for the initial window.")
@click.option("--dir", "start_dir", default=None, help="Working directory.")
@click.option("--detach", is_flag=True, help="Create headless (no Terminal window).")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
def create(name: str, window: str | None, start_dir: str | None, detach: bool, as_json: bool):
    """Create a new tmux session.

    Opens a new Terminal window attached to the session by default.
    Use --detach for headless sessions.
    """
    try:
        tmux.create_session(
            name, window_name=window, start_directory=start_dir, detach=detach
        )
        emit(
            {"ok": True, "action": "create", "session": name, "detach": detach},
            json=as_json,
            human_lines=f"Created session: {name}" + (" (detached)" if detach else " (Terminal window opened)"),
        )
    except DriveError as e:
        emit_error(e, json=as_json)


@session.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
def list_cmd(as_json: bool):
    """List all tmux sessions."""
    try:
        sessions = tmux.list_sessions()
        if as_json:
            emit(
                {"ok": True, "sessions": [s.to_dict() for s in sessions]},
                json=True,
                human_lines="",
            )
        else:
            if not sessions:
                click.echo("No tmux sessions.")
            else:
                for s in sessions:
                    attached = " (attached)" if s.attached else ""
                    click.echo(
                        f"  {s.name:<20} {s.windows} window(s)  {s.created}{attached}"
                    )
    except DriveError as e:
        emit_error(e, json=as_json)


@session.command()
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
def kill(name: str, as_json: bool):
    """Kill a tmux session."""
    try:
        tmux.kill_session(name)
        emit(
            {"ok": True, "action": "kill", "session": name},
            json=as_json,
            human_lines=f"Killed session: {name}",
        )
    except DriveError as e:
        emit_error(e, json=as_json)
