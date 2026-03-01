from __future__ import annotations

import shutil
import sys
from pathlib import Path

import click
from rich.console import Console

from doc_to_abstract import __version__
from doc_to_abstract.client import generate_abstract
from doc_to_abstract.config import load_config
from doc_to_abstract.exceptions import DocToAbstractError
from doc_to_abstract.latex import render_latex
from doc_to_abstract.prompt import build_prompt
from doc_to_abstract.template import fill_template

console = Console()

EXAMPLE_YAML = Path(__file__).resolve().parent.parent / "doc-to-abstract.example.yaml"


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Generate academic abstracts from presentation slides using Claude Code."""


@cli.command()
@click.argument("config_file", type=click.Path(), default="doc-to-abstract.yaml")
@click.option("--slides", type=click.Path(exists=True), multiple=True, help="Main material path(s) (.pdf/.pptx); can be repeated")
@click.option("--supplementary", type=click.Path(exists=True), multiple=True, help="Supplementary material(s) (.pdf/.pptx); can be repeated")
@click.option("--template", type=click.Path(exists=True), default=None, help="Conference/workshop template file (.tex or .docx)")
@click.option("--output", "-o", type=str, default=None, help="Override output file path")
@click.option("--language", type=str, default=None, help="Override language")
@click.option("--tone", type=str, default=None, help="Override tone")
@click.option("--max-words", type=int, default=None, help="Override max word count")
@click.option("--max-characters", type=int, default=None, help="Override max character count")
@click.option("--extra-instructions", type=str, multiple=True, help="Extra instruction(s); can be repeated")
@click.option("--body-only", is_flag=True, help="Output only the abstract block")
def generate(
    config_file: str,
    slides: tuple[str, ...],
    supplementary: tuple[str, ...],
    template: str | None,
    output: str | None,
    language: str | None,
    tone: str | None,
    max_words: int | None,
    max_characters: int | None,
    extra_instructions: tuple[str, ...],
    body_only: bool,
) -> None:
    """Generate an abstract from presentation materials.

    CONFIG_FILE defaults to doc-to-abstract.yaml in the current directory.
    """
    try:
        overrides: dict = {}
        if slides:
            overrides["slides"] = list(slides)
        if supplementary:
            overrides["supplementary"] = list(supplementary)
        if template:
            overrides["template"] = template
        if output:
            overrides["output"] = output
        if language:
            overrides["language"] = language
        if tone:
            overrides["tone"] = tone
        if max_words is not None:
            overrides["max_words"] = max_words
        if max_characters is not None:
            overrides["max_characters"] = max_characters
        if extra_instructions:
            overrides["extra_instructions"] = list(extra_instructions)

        console.print("[bold]Loading configuration...[/bold]")
        config = load_config(config_file, overrides=overrides)

        console.print(f"  Title:    {config.title}")
        console.print(f"  Authors:  {', '.join(a.name for a in config.authors)}")
        console.print(f"  Slides:   {len(config.slides)} file(s)")
        console.print(f"  Language: {config.language}")
        console.print(f"  Tone:     {config.tone}")
        if config.max_words:
            console.print(f"  Limit:    {config.max_words} words")
        elif config.max_characters:
            console.print(f"  Limit:    {config.max_characters} characters")
        if config.references:
            console.print(f"  Refs:     {len(config.references)} file(s)")
        if config.supplementary:
            console.print(f"  Suppl.:   {len(config.supplementary)} file(s)")
        if config.template:
            console.print(f"  Template: {config.template}")
        if config.extra_instructions:
            console.print(f"  Extra:    {len(config.extra_instructions)} instruction(s)")
        console.print()

        console.print("[bold blue]Building prompt...[/bold blue]")
        prompt = build_prompt(config)

        console.print("[bold blue]Calling Claude Code...[/bold blue]")
        abstract_text = generate_abstract(prompt)

        output_path = config.output

        # If a fillable template (.tex or .docx) is provided, write into it
        if config.template and Path(config.template).suffix.lower() in (".tex", ".docx"):
            console.print("[bold blue]Filling template...[/bold blue]")
            fill_template(config.template, abstract_text, output_path)
        else:
            console.print("[bold blue]Generating LaTeX...[/bold blue]")
            latex_output = render_latex(abstract_text, config, body_only=body_only)
            Path(output_path).write_text(latex_output, encoding="utf-8")

        console.print(f"\n[bold green]Done![/bold green] Abstract written to: [cyan]{output_path}[/cyan]")

    except DocToAbstractError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.command()
def init() -> None:
    """Create a sample doc-to-abstract.yaml in the current directory."""
    dest = Path("doc-to-abstract.yaml")
    if dest.exists():
        console.print(f"[yellow]Warning:[/yellow] {dest} already exists. Skipping.")
        return

    shutil.copy2(EXAMPLE_YAML, dest)
    console.print(f"[green]Created:[/green] {dest}")
    console.print("Edit this file with your paper details, then run:")
    console.print("  [cyan]doc-to-abstract generate[/cyan]")


@cli.command()
@click.option("--port", type=int, default=7860, help="Port number")
def serve(port: int) -> None:
    """Launch the Web UI."""
    from doc_to_abstract.server import launch

    console.print(f"[bold blue]Starting Web UI on port {port}...[/bold blue]")
    launch(port=port)


if __name__ == "__main__":
    cli()
