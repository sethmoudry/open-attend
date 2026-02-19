"""Prompt loader — reads .md files from this directory and exports prompt constants.

Each .md file uses '# PROMPT_NAME' H1 headers as delimiters.
The text between headers (stripped) becomes the prompt string.
"""

import re
from pathlib import Path

_DIR = Path(__file__).parent
_PROMPT_HEADER = re.compile(r"^#\s+([A-Z][A-Z0-9_]+)\s*$", re.MULTILINE)


def _load_prompts_from_file(filename: str) -> dict[str, str]:
    """Parse a single .md file into {PROMPT_NAME: prompt_text} pairs."""
    path = _DIR / filename
    content = path.read_text(encoding="utf-8")

    headers = list(_PROMPT_HEADER.finditer(content))
    prompts: dict[str, str] = {}
    for i, match in enumerate(headers):
        name = match.group(1)
        start = match.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(content)
        prompts[name] = content[start:end].strip()
    return prompts


def _load_all() -> dict[str, str]:
    """Load every .md file in the agents directory."""
    all_prompts: dict[str, str] = {}
    for md_file in sorted(_DIR.glob("*.md")):
        all_prompts.update(_load_prompts_from_file(md_file.name))
    return all_prompts


_ALL_PROMPTS = _load_all()

# Export every prompt as a module-level constant
globals().update(_ALL_PROMPTS)

__all__ = list(_ALL_PROMPTS.keys())
