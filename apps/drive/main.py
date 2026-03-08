"""Drive CLI — Terminal automation for AI agents. Programmatic tmux control."""
import click

from commands.session import session
from commands.run import run
from commands.send import send
from commands.logs import logs
from commands.poll import poll
from commands.fanout import fanout


@click.group()
@click.version_option(version="0.1.0", prog_name="drive")
def cli():
    """Terminal automation CLI for AI agents. Programmatic tmux control."""
    pass


cli.add_command(session)
cli.add_command(run)
cli.add_command(send)
cli.add_command(logs)
cli.add_command(poll)
cli.add_command(fanout)


if __name__ == "__main__":
    cli()
