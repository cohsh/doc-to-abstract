from __future__ import annotations

import tempfile
from pathlib import Path

import gradio as gr

from doc_to_abstract.client import generate_abstract
from doc_to_abstract.config import Author, Config, FileAnnotation
from doc_to_abstract.latex import render_latex
from doc_to_abstract.prompt import build_prompt
from doc_to_abstract.template import fill_template


def _collect_files(
    slides: list[str] | None,
    references: list[str] | None,
    supplementary: list[str] | None,
) -> list[list[str]]:
    """Build annotation table rows from uploaded files."""
    rows: list[list[str]] = []
    for f in (slides or []):
        if f:
            rows.append([Path(f).name, "slides", "medium", ""])
    for f in (references or []):
        if f:
            rows.append([Path(f).name, "references", "medium", ""])
    for f in (supplementary or []):
        if f:
            rows.append([Path(f).name, "supplementary", "medium", ""])
    return rows


def _run(
    slides_files: list[str] | None,
    references_files: list[str] | None,
    supplementary_files: list[str] | None,
    template_file: str | None,
    title: str,
    authors_text: str,
    language: str,
    tone: str,
    max_words: int,
    annotation_data: list[list[str]] | None,
    extra_instructions: str,
    body_only: bool,
) -> tuple[str, str | None]:
    """Generate abstract and return (abstract_text, output_file_path)."""
    if not slides_files:
        raise gr.Error("At least one Slides PDF is required.")
    slides = [f for f in slides_files if f]
    if not slides:
        raise gr.Error("At least one Slides PDF is required.")
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

    references = [f for f in (references_files or []) if f]
    supplementary = [f for f in (supplementary_files or []) if f]

    # Parse extra instructions (one per line)
    extra_list = [
        line.strip() for line in extra_instructions.splitlines() if line.strip()
    ]

    # Build annotations from dataframe data
    annotations: dict[str, FileAnnotation] = {}
    if annotation_data:
        # Build a map from filename to full path
        name_to_path: dict[str, str] = {}
        for f in slides:
            name_to_path[Path(f).name] = f
        for f in references:
            name_to_path[Path(f).name] = f
        for f in supplementary:
            name_to_path[Path(f).name] = f

        for row in annotation_data:
            if len(row) >= 4:
                filename, _category, importance, comment = row[0], row[1], row[2], row[3]
                importance = str(importance).lower().strip()
                if importance not in ("high", "medium", "low"):
                    importance = "medium"
                comment = str(comment).strip()
                filepath = name_to_path.get(filename, filename)
                annotations[filepath] = FileAnnotation(
                    importance=importance, comment=comment
                )

    config = Config(
        title=title.strip(),
        authors=authors,
        slides=slides,
        language=language,
        tone=tone,
        max_words=max_words if max_words > 0 else None,
        references=references,
        supplementary=supplementary,
        template=template_file or "",
        extra_instructions=extra_list,
        annotations=annotations,
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
    """Create the Gradio app with tabbed layout."""
    with gr.Blocks(title="doc-to-abstract") as app:
        gr.Markdown("# doc-to-abstract\nGenerate academic abstracts from presentation slides using Claude Code.")

        with gr.Row():
            with gr.Column():
                with gr.Tabs():
                    # Tab 1: Materials
                    with gr.Tab("1. Materials"):
                        slides_input = gr.File(
                            label="Slides PDF(s) (required)",
                            file_types=[".pdf"],
                            file_count="multiple",
                            type="filepath",
                        )
                        reference_input = gr.File(
                            label="Reference papers (optional)",
                            file_types=[".pdf"],
                            file_count="multiple",
                            type="filepath",
                        )
                        supplementary_input = gr.File(
                            label="Supplementary materials (optional, e.g., call for papers)",
                            file_types=[".pdf"],
                            file_count="multiple",
                            type="filepath",
                        )
                        template_input = gr.File(
                            label="Conference template (optional, .tex / .docx / .pdf)",
                            file_types=[".tex", ".docx", ".pdf"],
                            type="filepath",
                        )

                    # Tab 2: Paper Info
                    with gr.Tab("2. Paper Info"):
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

                    # Tab 3: Annotations & Generate
                    with gr.Tab("3. Annotations & Generate"):
                        gr.Markdown("Edit importance and comments for each uploaded file. Changes are reflected in the prompt.")
                        annotation_table = gr.Dataframe(
                            headers=["Filename", "Category", "Importance", "Comment"],
                            datatype=["str", "str", "str", "str"],
                            column_count=(4, "fixed"),
                            interactive=True,
                            label="File Annotations",
                        )
                        refresh_btn = gr.Button("Refresh file list", variant="secondary", size="sm")

                        extra_input = gr.Textbox(
                            label="Extra instructions (optional, one per line)",
                            placeholder="Focus on the numerical results.\nEmphasize the novelty of the method.",
                            lines=3,
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

        # Refresh annotation table from uploaded files
        refresh_btn.click(
            fn=_collect_files,
            inputs=[slides_input, reference_input, supplementary_input],
            outputs=[annotation_table],
        )

        # Auto-refresh when files change
        for file_input in [slides_input, reference_input, supplementary_input]:
            file_input.change(
                fn=_collect_files,
                inputs=[slides_input, reference_input, supplementary_input],
                outputs=[annotation_table],
            )

        # Generate
        generate_btn.click(
            fn=_run,
            inputs=[
                slides_input,
                reference_input,
                supplementary_input,
                template_input,
                title_input,
                authors_input,
                language_input,
                tone_input,
                max_words_input,
                annotation_table,
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
