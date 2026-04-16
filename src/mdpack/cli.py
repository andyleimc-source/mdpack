"""mdpack CLI entry point (placeholder)."""

from __future__ import annotations

import click

from . import __version__


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="mdpack")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Convert any directory of docs to clean Markdown.

    This is a 0.0.1 placeholder release to reserve the name on PyPI.
    Real conversion commands will land in 0.1.0. Track progress at
    https://github.com/andyleimc-source/mdpack.
    """
    if ctx.invoked_subcommand is None:
        click.echo(
            f"mdpack {__version__} — placeholder release, no conversion yet. "
            "See https://github.com/andyleimc-source/mdpack for roadmap."
        )
