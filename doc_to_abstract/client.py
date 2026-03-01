from __future__ import annotations

import os
import subprocess

from doc_to_abstract.exceptions import APIError


def generate_abstract(prompt: str) -> str:
    """Call Claude Code CLI with a prompt and return the generated text."""
    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "text",
    ]

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
        )
    except subprocess.TimeoutExpired:
        raise APIError("Claude Code CLI timed out after 600 seconds")
    except FileNotFoundError:
        raise APIError(
            "Claude Code CLI not found. Install it with: npm install -g @anthropic-ai/claude-code"
        )

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[:1200]
        raise APIError(
            f"Claude Code CLI failed (exit code {result.returncode}): {detail}"
        )

    text = result.stdout.strip()
    if not text:
        raise APIError("Claude Code CLI returned empty output")
    return text
