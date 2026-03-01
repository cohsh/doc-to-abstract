from __future__ import annotations

import tempfile
from pathlib import Path

import gradio as gr

from doc_to_abstract.client import generate_abstract
from doc_to_abstract.config import Author, Config
from doc_to_abstract.latex import render_latex
from doc_to_abstract.prompt import build_prompt
from doc_to_abstract.template import fill_template, read_template


def _run(
    slides_pdf: str | None,
    title: str,
    authors_text: str,
    language: str,
    tone: str,
    max_words: int,
    template_file: str | None,
    reference_files: list[str] | None,
    extra_instructions: str,
    body_only: bool,
) -> tuple[str, str | None]:
    """Generate abstract and return (abstract_text, output_file_path)."""
    if not slides_pdf:
        raise gr.Error("Slides PDF is required.")
    if not title.strip():
        raise gr.Error("Title is required.")
    if not authors_text.strip():
        raise gr.Error("At least one author is required.")

    # Parse authors (one per line: "Name, Affiliation")
    authors = []
    for line in authors_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",", 1)]
        if len(parts) < 2:
            raise gr.Error(f"Invalid author format: '{line}'. Use: Name, Affiliation")
        authors.append(Author(name=parts[0], affiliation=parts[1]))

    if not authors:
        raise gr.Error("At least one author is required.")

    references = []
    if reference_files:
        references = [f for f in reference_files if f]

    config = Config(
        title=title.strip(),
        authors=authors,
        slides_pdf=slides_pdf,
        language=language,
        tone=tone,
        max_words=max_words if max_words > 0 else None,
        references=references,
        template=template_file or "",
        extra_instructions=extra_instructions.strip(),
    )

    prompt = build_prompt(config)
    abstract_text = generate_abstract(prompt)

    # Generate output file
    if config.template and Path(config.template).suffix.lower() in (".tex", ".docx"):
        suffix = Path(config.template).suffix.lower()
        out = tempfile.NamedTemporaryFile(
            suffix=suffix, prefix="abstract_", delete=False
        )
        out.close()
        fill_template(config.template, abstract_text, out.name)
        return abstract_text, out.name
    else:
        latex_output = render_latex(abstract_text, config, body_only=body_only)
        out = tempfile.NamedTemporaryFile(
            suffix=".tex", prefix="abstract_", delete=False
        )
        out.close()
        Path(out.name).write_text(latex_output, encoding="utf-8")
        return abstract_text, out.name


def create_app() -> gr.Blocks:
    """Create the Gradio app."""
    with gr.Blocks(title="doc-to-abstract") as app:
        gr.Markdown("# doc-to-abstract\nGenerate academic abstracts from presentation slides using Claude Code.")

        with gr.Row():
            with gr.Column():
                slides_input = gr.File(
                    label="Slides PDF (required)",
                    file_types=[".pdf"],
                    type="filepath",
                )
                title_input = gr.Textbox(
                    label="Title (required)",
                    placeholder="My Research Title",
                )
                authors_input = gr.Textbox(
                    label="Authors (one per line: Name, Affiliation)",
                    placeholder="Alice Example, Example University\nBob Sample, Example Institute",
                    lines=3,
                )

                with gr.Row():
                    language_input = gr.Dropdown(
                        label="Language",
                        choices=["English", "Japanese", "Chinese", "Korean", "German", "French", "Spanish"],
                        value="English",
                    )
                    tone_input = gr.Dropdown(
                        label="Tone",
                        choices=["formal", "semi-formal", "casual"],
                        value="formal",
                    )
                    max_words_input = gr.Number(
                        label="Max words (0 = no limit)",
                        value=300,
                        precision=0,
                    )

                template_input = gr.File(
                    label="Conference template (optional, .tex / .docx / .pdf)",
                    file_types=[".tex", ".docx", ".pdf"],
                    type="filepath",
                )
                reference_input = gr.File(
                    label="Reference papers (optional)",
                    file_types=[".pdf"],
                    file_count="multiple",
                    type="filepath",
                )
                extra_input = gr.Textbox(
                    label="Extra instructions (optional)",
                    placeholder="Focus on the numerical results.",
                    lines=2,
                )
                body_only_input = gr.Checkbox(
                    label="Body only (no full LaTeX document)",
                    value=False,
                )

                generate_btn = gr.Button("Generate Abstract", variant="primary")

            with gr.Column():
                abstract_output = gr.Textbox(
                    label="Generated Abstract",
                    lines=12,
                )
                file_output = gr.File(label="Download output file")

        generate_btn.click(
            fn=_run,
            inputs=[
                slides_input,
                title_input,
                authors_input,
                language_input,
                tone_input,
                max_words_input,
                template_input,
                reference_input,
                extra_input,
                body_only_input,
            ],
            outputs=[abstract_output, file_output],
        )

    return app


def launch(port: int = 7860) -> None:
    """Launch the Gradio app."""
    app = create_app()
    app.launch(server_port=port)
