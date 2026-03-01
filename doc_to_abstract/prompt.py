from __future__ import annotations

from pathlib import Path

import pymupdf

from doc_to_abstract.config import Config
from doc_to_abstract.exceptions import PDFError
from doc_to_abstract.template import read_template

from doc_to_abstract.config import FileAnnotation

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _format_annotation(annotations: dict[str, FileAnnotation], filepath: str) -> str:
    """Format annotation metadata for a file, if any."""
    ann = annotations.get(filepath) or annotations.get(Path(filepath).name)
    if not ann:
        return ""
    parts = []
    if ann.importance != "medium":
        parts.append(f"[Importance: {ann.importance}]")
    if ann.comment:
        parts.append(f"[Note: {ann.comment}]")
    return " ".join(parts)


def extract_text_from_pdf(pdf_path: str, page_label: str = "Slide") -> str:
    """Extract text from a PDF file using PyMuPDF."""
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        raise PDFError(f"Failed to open PDF: {pdf_path}: {e}") from e

    pages = []
    for i, page in enumerate(doc, 1):
        text = page.get_text().strip()
        if text:
            pages.append(f"--- {page_label} {i} ---\n{text}")
    doc.close()

    if not pages:
        raise PDFError(f"No text could be extracted from: {pdf_path}")

    return "\n\n".join(pages)


def build_prompt(config: Config) -> str:
    """Build the full prompt for abstract generation."""
    template_path = PROMPTS_DIR / "system_prompt.txt"
    template = template_path.read_text(encoding="utf-8")

    # Format authors
    author_lines = []
    for a in config.authors:
        line = f"  - {a.name} ({a.affiliation})"
        if a.email:
            line += f" <{a.email}>"
        author_lines.append(line)
    authors_text = "\n".join(author_lines)

    # Build length constraint
    length_constraint = ""
    if config.max_words:
        length_constraint = f"- The abstract MUST NOT exceed {config.max_words} words."
    elif config.max_characters:
        length_constraint = f"- The abstract MUST NOT exceed {config.max_characters} characters."

    prompt = template.format(
        language=config.language,
        tone=config.tone,
        title=config.title,
        authors=authors_text,
        length_constraint=length_constraint,
    )

    # Append extra instructions
    if config.extra_instructions:
        extra_text = "\n".join(f"- {inst}" for inst in config.extra_instructions)
        prompt += f"\n\n## Additional Instructions\n{extra_text}\n"

    # Append extracted slide text
    for i, slide_path in enumerate(config.slides, 1):
        slides_text = extract_text_from_pdf(slide_path, page_label="Slide")
        ann_text = _format_annotation(config.annotations, slide_path)
        if len(config.slides) > 1:
            header = f"\n\n## Presentation Slides (Deck #{i}: {Path(slide_path).name})"
        else:
            header = "\n\n## Presentation Slides Content"
        if ann_text:
            header += f"\n{ann_text}"
        prompt += f"{header}\n{slides_text}\n"

    # Append reference papers
    for i, ref_path in enumerate(config.references, 1):
        ref_text = extract_text_from_pdf(ref_path)
        ann_text = _format_annotation(config.annotations, ref_path)
        header = f"\n## Reference Paper #{i} ({Path(ref_path).name})"
        if ann_text:
            header += f"\n{ann_text}"
        prompt += f"{header}\n{ref_text}\n"

    # Append supplementary materials
    for i, sup_path in enumerate(config.supplementary, 1):
        sup_text = extract_text_from_pdf(sup_path, page_label="Page")
        ann_text = _format_annotation(config.annotations, sup_path)
        header = f"\n## Supplementary Material #{i} ({Path(sup_path).name})"
        if ann_text:
            header += f"\n{ann_text}"
        prompt += f"{header}\n{sup_text}\n"

    # Append template content
    if config.template:
        template_text = read_template(config.template)
        prompt += (
            "\n## Submission Template\n"
            "The following is the submission template provided by the conference/workshop organizers. "
            "Use it to understand the required format, structure, length constraints, and any specific guidelines.\n\n"
            f"{template_text}\n"
        )

    return prompt
