import re
from typing import Tuple, Dict

import yaml


def parse_frontmatter(content: str) -> Tuple[Dict, str]:
    """Parse YAML frontmatter from markdown content.
    Returns (frontmatter_dict, body_without_frontmatter).
    """
    pattern = r"^---\s*\n(.*?)\n---\s*\n?"
    match = re.match(pattern, content, re.DOTALL)
    if not match:
        return {}, content

    fm_text = match.group(1)
    body = content[match.end():]

    try:
        fm = yaml.safe_load(fm_text)
        if not isinstance(fm, dict):
            return {}, content
    except yaml.YAMLError:
        return {}, content

    return fm, body


def add_frontmatter(body: str, metadata: dict) -> str:
    """Wrap body with YAML frontmatter."""
    fm_text = yaml.dump(metadata, default_flow_style=False, allow_unicode=True).strip()
    return f"---\n{fm_text}\n---\n\n{body}"
