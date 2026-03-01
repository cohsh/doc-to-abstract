from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from doc_to_abstract.exceptions import ConfigError

MAX_PDF_SIZE = 32 * 1024 * 1024  # 32 MB


@dataclass
class Author:
    name: str
    affiliation: str
    email: str = ""


@dataclass
class Config:
    title: str
    authors: list[Author]
    slides_pdf: str
    language: str = "English"
    tone: str = "formal"
    max_words: int | None = None
    max_characters: int | None = None
    references: list[str] = field(default_factory=list)
    template: str = ""
    output: str = "abstract.tex"
    extra_instructions: str = ""


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
    if not data.get("slides_pdf"):
        raise ConfigError("'slides_pdf' is required")

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

    # Validate slides PDF
    slides_path = Path(data["slides_pdf"])
    if not slides_path.exists():
        raise ConfigError(f"Slides PDF not found: {data['slides_pdf']}")
    if slides_path.stat().st_size > MAX_PDF_SIZE:
        raise ConfigError(f"Slides PDF exceeds 32MB limit: {data['slides_pdf']}")

    # Validate references
    references = data.get("references", []) or []
    for ref_path in references:
        p = Path(ref_path)
        if not p.exists():
            raise ConfigError(f"Reference PDF not found: {ref_path}")
        if p.stat().st_size > MAX_PDF_SIZE:
            raise ConfigError(f"Reference PDF exceeds 32MB limit: {ref_path}")

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

    return Config(
        title=data["title"],
        authors=authors,
        slides_pdf=str(slides_path),
        language=data.get("language", "English"),
        tone=data.get("tone", "formal"),
        max_words=max_words,
        max_characters=max_characters,
        references=references,
        template=template,
        output=data.get("output", "abstract.tex"),
        extra_instructions=data.get("extra_instructions", ""),
    )
