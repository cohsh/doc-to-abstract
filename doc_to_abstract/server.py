from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import gradio as gr
import yaml

from doc_to_abstract.client import generate_abstract
from doc_to_abstract.config import Author, Config, FileAnnotation
from doc_to_abstract.latex import render_latex
from doc_to_abstract.prompt import build_prompt
from doc_to_abstract.template import fill_template

MATERIALS_DIR = Path("materials")
CONFIG_FILE = Path("doc-to-abstract.yaml")


def _merge_annotations(
    slides: list[str] | None,
    references: list[str] | None,
    supplementary: list[str] | None,
    current_table,
) -> list[list[str]]:
    """Merge uploaded files with existing annotation table, preserving edits."""
    # Build desired file list
    desired: list[tuple[str, str]] = []  # (filename, category)
    for f in (slides or []):
        if f:
            desired.append((Path(f).name, "slides"))
    for f in (references or []):
        if f:
            desired.append((Path(f).name, "references"))
    for f in (supplementary or []):
        if f:
            desired.append((Path(f).name, "supplementary"))

    # Read existing annotations into a map keyed by (filename, category)
    existing: dict[tuple[str, str], tuple[str, str]] = {}
    if current_table is not None:
        rows = current_table.values.tolist() if hasattr(current_table, "values") else current_table
        for row in (rows or []):
            if len(row) >= 4:
                key = (str(row[0]).strip(), str(row[1]).strip())
                existing[key] = (str(row[2]).strip(), str(row[3]).strip())

    # Build merged result: keep existing importance/comment, default for new files
    result: list[list[str]] = []
    for filename, category in desired:
        key = (filename, category)
        if key in existing:
            importance, comment = existing[key]
        else:
            importance, comment = "medium", ""
        result.append([filename, category, importance, comment])
    return result


def _copy_to_materials(src_path: str, category: str) -> str:
    """Copy an uploaded file into materials/<category>/ and return the relative path."""
    dest_dir = MATERIALS_DIR / category
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / Path(src_path).name
    if not dest.exists() or not dest.samefile(src_path):
        shutil.copy2(src_path, dest)
    return str(dest)


def _save_config(
    slides_files: list[str] | None,
    references_files: list[str] | None,
    supplementary_files: list[str] | None,
    template_file: str | None,
    title: str,
    authors_text: str,
    language: str,
    tone: str,
    max_words: int,
    annotation_data,
    extra_instructions: str,
    body_only: bool,
) -> str | None:
    """Save current UI state to doc-to-abstract.yaml, copying files to materials/."""
    data: dict = {}

    # Title
    data["title"] = title.strip()

    # Authors
    authors = []
    for line in (authors_text or "").strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",", 1)]
        if len(parts) >= 2:
            authors.append({"name": parts[0], "affiliation": parts[1]})
    data["authors"] = authors

    # Copy files and record paths
    slides = []
    for f in (slides_files or []):
        if f:
            slides.append(_copy_to_materials(f, "slides"))
    data["slides"] = slides

    refs = []
    for f in (references_files or []):
        if f:
            refs.append(_copy_to_materials(f, "references"))
    if refs:
        data["references"] = refs

    supps = []
    for f in (supplementary_files or []):
        if f:
            supps.append(_copy_to_materials(f, "supplementary"))
    if supps:
        data["supplementary"] = supps

    if template_file:
        data["template"] = _copy_to_materials(template_file, "templates")

    # Settings
    data["language"] = language
    data["tone"] = tone
    if max_words and max_words > 0:
        data["max_words"] = int(max_words)
    data["output"] = "abstract.tex"

    # Extra instructions
    extra_list = [
        line.strip() for line in (extra_instructions or "").splitlines() if line.strip()
    ]
    if extra_list:
        data["extra_instructions"] = extra_list

    # Annotations
    ann_dict: dict = {}
    if annotation_data is not None:
        rows = annotation_data.values.tolist() if hasattr(annotation_data, "values") else annotation_data
        for row in (rows or []):
            if len(row) >= 4:
                filename = str(row[0]).strip()
                importance = str(row[2]).lower().strip()
                comment = str(row[3]).strip()
                ann_entry: dict = {}
                if importance and importance != "medium":
                    ann_entry["importance"] = importance
                if comment:
                    ann_entry["comment"] = comment
                if ann_entry:
                    ann_dict[filename] = ann_entry
    if ann_dict:
        data["annotations"] = ann_dict

    CONFIG_FILE.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return str(CONFIG_FILE)


def _load_config(config_file: str | None):
    """Load a YAML config and return values for all UI fields."""
    if not config_file:
        raise gr.Error("No config file provided.")

    path = Path(config_file)
    if not path.exists():
        raise gr.Error(f"Config file not found: {config_file}")

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise gr.Error("Invalid config file.")

    # Title
    title = data.get("title", "")

    # Authors -> text format
    authors_lines = []
    for a in data.get("authors", []):
        if isinstance(a, dict):
            authors_lines.append(f"{a.get('name', '')}, {a.get('affiliation', '')}")
    authors_text = "\n".join(authors_lines)

    # Language, tone, max_words
    language = data.get("language", "English")
    tone = data.get("tone", "formal")
    max_words = data.get("max_words", 300) or 0

    # Extra instructions
    raw_extra = data.get("extra_instructions", [])
    if isinstance(raw_extra, str):
        extra_text = raw_extra
    elif isinstance(raw_extra, list):
        extra_text = "\n".join(str(e) for e in raw_extra)
    else:
        extra_text = ""

    # Slides files
    raw_slides = data.get("slides") or data.get("slides_pdf") or []
    if isinstance(raw_slides, str):
        raw_slides = [raw_slides]
    slides_files = [s for s in raw_slides if Path(s).exists()]

    # References
    raw_refs = data.get("references", []) or []
    ref_files = [r for r in raw_refs if Path(r).exists()]

    # Supplementary
    raw_supps = data.get("supplementary", []) or []
    supp_files = [s for s in raw_supps if Path(s).exists()]

    # Template
    template = data.get("template", "")
    template_file = template if template and Path(template).exists() else None

    # Annotations -> dataframe rows
    ann_rows: list[list[str]] = []
    raw_annotations = data.get("annotations", {}) or {}
    # Also build rows from file lists for files without annotations
    all_files: list[tuple[str, str]] = []
    for s in raw_slides:
        all_files.append((Path(s).name, "slides"))
    for r in raw_refs:
        all_files.append((Path(r).name, "references"))
    for s in raw_supps:
        all_files.append((Path(s).name, "supplementary"))

    for filename, category in all_files:
        ann = raw_annotations.get(filename, {})
        importance = ann.get("importance", "medium") if isinstance(ann, dict) else "medium"
        comment = ann.get("comment", "") if isinstance(ann, dict) else ""
        ann_rows.append([filename, category, importance, comment])

    # body_only is not stored in YAML, default to False
    body_only = False

    return (
        slides_files or None,
        ref_files or None,
        supp_files or None,
        template_file,
        title,
        authors_text,
        language,
        tone,
        max_words,
        ann_rows,
        extra_text,
        body_only,
    )


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
    annotation_data,
    extra_instructions: str,
    body_only: bool,
) -> tuple[str, str | None]:
    """Generate abstract and return (abstract_text, output_file_path)."""
    if not slides_files:
        raise gr.Error("At least one main material file is required.")
    slides = [f for f in slides_files if f]
    if not slides:
        raise gr.Error("At least one main material file is required.")
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
    # Handle both list and pandas DataFrame
    if annotation_data is not None:
        rows = annotation_data.values.tolist() if hasattr(annotation_data, "values") else annotation_data
        if rows:
            # Build a map from filename to full path
            name_to_path: dict[str, str] = {}
            for f in slides:
                name_to_path[Path(f).name] = f
            for f in references:
                name_to_path[Path(f).name] = f
            for f in supplementary:
                name_to_path[Path(f).name] = f

            for row in rows:
                if len(row) >= 4:
                    filename = str(row[0]).strip()
                    importance = str(row[2]).lower().strip()
                    if importance not in ("high", "medium", "low"):
                        importance = "medium"
                    comment = str(row[3]).strip()
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
            with gr.Column(scale=1):
                with gr.Tabs():
                    # Tab 1: Materials
                    with gr.Tab("1. Materials"):
                        slides_input = gr.File(
                            label="Main materials (required, e.g., slides, manuscripts)",
                            file_types=[".pdf", ".pptx"],
                            file_count="multiple",
                            type="filepath",
                        )
                        reference_input = gr.File(
                            label="Reference papers (optional)",
                            file_types=[".pdf", ".pptx"],
                            file_count="multiple",
                            type="filepath",
                        )
                        supplementary_input = gr.File(
                            label="Supplementary materials (optional, e.g., call for papers)",
                            file_types=[".pdf", ".pptx"],
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
                        gr.Markdown("---")
                        with gr.Row():
                            save_btn = gr.Button("Save config", variant="secondary", size="sm")
                            load_input = gr.File(
                                label="Load config (.yaml)",
                                file_types=[".yaml", ".yml"],
                                type="filepath",
                            )
                        config_download = gr.File(label="Saved config file", visible=False)

                    # Tab 3: Annotations & Generate
                    with gr.Tab("3. Annotations & Generate"):
                        gr.Markdown(
                            "Edit **Importance** (`high` / `medium` / `low`) and **Comment** for each file. "
                            "Filename and Category are read-only."
                        )
                        annotation_table = gr.Dataframe(
                            headers=["Filename", "Category", "Importance", "Comment"],
                            datatype=["str", "str", "str", "str"],
                            column_count=(4, "fixed"),
                            column_widths=["25%", "15%", "15%", "45%"],
                            interactive=True,
                            label="File Annotations",
                            wrap=True,
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

            with gr.Column(scale=1):
                abstract_output = gr.Textbox(
                    label="Generated Abstract",
                    lines=12,
                )
                file_output = gr.File(label="Download output file")

        # Refresh annotation table from uploaded files (preserving edits)
        refresh_btn.click(
            fn=_merge_annotations,
            inputs=[slides_input, reference_input, supplementary_input, annotation_table],
            outputs=[annotation_table],
        )

        # Auto-refresh when files change (preserving edits)
        for file_input in [slides_input, reference_input, supplementary_input]:
            file_input.change(
                fn=_merge_annotations,
                inputs=[slides_input, reference_input, supplementary_input, annotation_table],
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

        # Save config
        save_btn.click(
            fn=_save_config,
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
            outputs=[config_download],
        ).then(
            fn=lambda f: gr.update(visible=True) if f else gr.update(),
            inputs=[config_download],
            outputs=[config_download],
        )

        # Load config
        load_input.change(
            fn=_load_config,
            inputs=[load_input],
            outputs=[
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
        )

    return app


def launch(port: int = 7860) -> None:
    """Launch the Gradio app."""
    app = create_app()
    app.launch(server_port=port)
