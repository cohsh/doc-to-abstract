from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from doc_to_abstract.exceptions import ConfigError

MAX_FILE_SIZE = 32 * 1024 * 1024  # 32 MB


@dataclass
class Author:
    name: str
    affiliation: str
    email: str = ""


@dataclass
class FileAnnotation:
    importance: str = "medium"  # high / medium / low
    comment: str = ""


@dataclass
class Config:
    title: str
    authors: list[Author]
    slides: list[str]
    language: str = "English"
    tone: str = "formal"
    max_words: int | None = None
    max_characters: int | None = None
    references: list[str] = field(default_factory=list)
    supplementary: list[str] = field(default_factory=list)
    template: str = ""
    output: str = "abstract.tex"
    extra_instructions: list[str] = field(default_factory=list)
    annotations: dict[str, FileAnnotation] = field(default_factory=dict)


def load_config(config_path: str, overrides: dict | None = None) -> Config:
    """Load and validate YAML config, applying CLI overrides."""
    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ConfigError(f"Invalid config file: {config_path}")

    # Apply CLI overrides
    if overrides:
        for key, value in overrides.items():
            if value is not None:
                data[key] = value

    # Validate required fields
    if not data.get("title"):
        raise ConfigError("'title' is required")
    if not data.get("authors"):
        raise ConfigError("'authors' is required (at least one author)")

    # Parse authors
    authors = []
    for i, author_data in enumerate(data["authors"]):
        if not isinstance(author_data, dict):
            raise ConfigError(f"Author #{i + 1}: must be a mapping with 'name' and 'affiliation'")
        if not author_data.get("name"):
            raise ConfigError(f"Author #{i + 1}: 'name' is required")
        if not author_data.get("affiliation"):
            raise ConfigError(f"Author #{i + 1}: 'affiliation' is required")
        authors.append(Author(
            name=author_data["name"],
            affiliation=author_data["affiliation"],
            email=author_data.get("email", ""),
        ))

    # Validate slides (backward compatible: accept slides_pdf or slides)
    raw_slides = data.get("slides")
    raw_slides_pdf = data.get("slides_pdf")
    if raw_slides and raw_slides_pdf:
        raise ConfigError("Use either 'slides' or 'slides_pdf', not both")
    if raw_slides_pdf is not None:
        raw_slides = raw_slides_pdf
    if not raw_slides:
        raise ConfigError("'slides' is required (at least one file)")
    if isinstance(raw_slides, str):
        slides_list = [raw_slides]
    elif isinstance(raw_slides, list):
        slides_list = raw_slides
    else:
        raise ConfigError("'slides' must be a string or a list of strings")
    if not slides_list:
        raise ConfigError("'slides' must contain at least one file path")
    for s_path in slides_list:
        p = Path(s_path)
        if not p.exists():
            raise ConfigError(f"File not found: {s_path}")
        if p.stat().st_size > MAX_FILE_SIZE:
            raise ConfigError(f"File exceeds 32MB limit: {s_path}")

    # Validate references
    references = data.get("references", []) or []
    for ref_path in references:
        p = Path(ref_path)
        if not p.exists():
            raise ConfigError(f"Reference file not found: {ref_path}")
        if p.stat().st_size > MAX_FILE_SIZE:
            raise ConfigError(f"Reference file exceeds 32MB limit: {ref_path}")

    # Validate supplementary materials
    supplementary = data.get("supplementary", []) or []
    for sup_path in supplementary:
        p = Path(sup_path)
        if not p.exists():
            raise ConfigError(f"Supplementary file not found: {sup_path}")
        if p.stat().st_size > MAX_FILE_SIZE:
            raise ConfigError(f"Supplementary file exceeds 32MB limit: {sup_path}")

    # Validate mutual exclusivity of max_words and max_characters
    max_words = data.get("max_words")
    max_characters = data.get("max_characters")
    if max_words and max_characters:
        raise ConfigError("'max_words' and 'max_characters' are mutually exclusive")

    # Validate template file
    template = data.get("template", "")
    if template:
        template_path = Path(template)
        if not template_path.exists():
            raise ConfigError(f"Template file not found: {template}")
        suffix = template_path.suffix.lower()
        if suffix not in (".tex", ".docx", ".pdf"):
            raise ConfigError(f"Unsupported template format: {suffix} (use .tex, .docx, or .pdf)")

    # Normalize extra_instructions (backward compatible: accept string or list)
    raw_extra = data.get("extra_instructions", [])
    if isinstance(raw_extra, str):
        extra_instructions = [raw_extra] if raw_extra.strip() else []
    elif isinstance(raw_extra, list):
        extra_instructions = [str(e).strip() for e in raw_extra if str(e).strip()]
    else:
        extra_instructions = []

    # Parse annotations
    annotations: dict[str, FileAnnotation] = {}
    raw_annotations = data.get("annotations", {}) or {}
    if isinstance(raw_annotations, dict):
        for filepath, ann_data in raw_annotations.items():
            if isinstance(ann_data, dict):
                importance = str(ann_data.get("importance", "medium")).lower()
                if importance not in ("high", "medium", "low"):
                    importance = "medium"
                annotations[filepath] = FileAnnotation(
                    importance=importance,
                    comment=str(ann_data.get("comment", "")),
                )

    return Config(
        title=data["title"],
        authors=authors,
        slides=[str(Path(s)) for s in slides_list],
        language=data.get("language", "English"),
        tone=data.get("tone", "formal"),
        max_words=max_words,
        max_characters=max_characters,
        references=references,
        supplementary=supplementary,
        template=template,
        output=data.get("output", "abstract.tex"),
        extra_instructions=extra_instructions,
        annotations=annotations,
    )
