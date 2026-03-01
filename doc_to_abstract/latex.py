from __future__ import annotations

from doc_to_abstract.config import Config

# LaTeX special characters to escape in user-provided metadata
_LATEX_SPECIAL = [
    ("\\", "\\textbackslash{}"),
    ("&", "\\&"),
    ("%", "\\%"),
    ("$", "\\$"),
    ("#", "\\#"),
    ("_", "\\_"),
    ("{", "\\{"),
    ("}", "\\}"),
    ("~", "\\textasciitilde{}"),
    ("^", "\\textasciicircum{}"),
]


def _escape_latex(text: str) -> str:
    """Escape LaTeX special characters in user-provided metadata."""
    for old, new in _LATEX_SPECIAL:
        text = text.replace(old, new)
    return text


def render_latex(abstract_text: str, config: Config, body_only: bool = False) -> str:
    """Render the abstract as a LaTeX document or abstract block."""
    body = abstract_text.strip()

    if body_only:
        return f"\\begin{{abstract}}\n{body}\n\\end{{abstract}}\n"

    # Escape only user-provided metadata (title, author names, affiliations)
    title = _escape_latex(config.title)

    author_entries = []
    for a in config.authors:
        name = _escape_latex(a.name)
        affiliation = _escape_latex(a.affiliation)
        entry = f"  {name} \\\\\n  {affiliation}"
        if a.email:
            email = _escape_latex(a.email)
            entry += f" \\\\\n  \\texttt{{{email}}}"
        author_entries.append(entry)

    authors_block = " \\and\n".join(author_entries)

    return (
        "\\documentclass{article}\n"
        "\\usepackage[utf8]{inputenc}\n"
        "\n"
        f"\\title{{{title}}}\n"
        f"\\author{{\n{authors_block}\n}}\n"
        "\\date{}\n"
        "\n"
        "\\begin{document}\n"
        "\\maketitle\n"
        "\n"
        "\\begin{abstract}\n"
        f"{body}\n"
        "\\end{abstract}\n"
        "\n"
        "\\end{document}\n"
    )
