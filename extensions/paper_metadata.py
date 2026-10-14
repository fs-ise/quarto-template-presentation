from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from copier_template_extensions import ContextHook


def _author_name(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, (list, tuple)):
        return ", ".join(name for item in value if (name := _author_name(item)))

    if not isinstance(value, dict):
        return ""

    name = value.get("name", value)
    if isinstance(name, str):
        return name.strip()
    if not isinstance(name, dict):
        return ""

    literal = name.get("literal")
    if isinstance(literal, str) and literal.strip():
        return literal.strip()

    given = name.get("given") or name.get("given-names")
    family = name.get("family") or name.get("family-names")
    return " ".join(part.strip() for part in (given, family) if isinstance(part, str) and part.strip())


def _parse_front_matter(path: Path) -> dict[str, Any]:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return {}
    if not lines or lines[0].strip() != "---":
        return {}

    end = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() in {"---", "..."}),
        None,
    )
    if end is None:
        return {}

    try:
        metadata = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError:
        return {}
    return metadata if isinstance(metadata, dict) else {}


def _find_paper_qmd(destination: Path) -> Path | None:
    for directory in (destination, *destination.parents):
        paper_qmd = directory / "paper.qmd"
        if paper_qmd.is_file():
            return paper_qmd
        if (directory / ".git").exists():
            break
    return None


class PaperMetadata(ContextHook):
    _cache: dict[Path, dict[str, str | None]] = {}

    def hook(self, context: dict[str, Any]) -> None:
        copier_conf = context.get("_copier_conf")
        if copier_conf is None:
            destination = None
        elif hasattr(copier_conf, "get"):
            destination = copier_conf.get("dst_path")
        else:
            destination = getattr(copier_conf, "dst_path", None)
        if destination is None:
            metadata = {"paper_title": None, "paper_author": None}
        else:
            destination_path = Path(destination).expanduser().resolve()
            if destination_path not in self._cache:
                self._cache[destination_path] = self._read_paper_metadata(destination_path)
            metadata = self._cache[destination_path]

        context.update(metadata)

    @staticmethod
    def _read_paper_metadata(destination: Path) -> dict[str, str | None]:
        paper_qmd = _find_paper_qmd(destination)
        if paper_qmd is None:
            return {"paper_title": None, "paper_author": None}

        metadata = _parse_front_matter(paper_qmd)
        title = metadata.get("title")
        return {
            "paper_title": title.strip() if isinstance(title, str) and title.strip() else None,
            "paper_author": _author_name(metadata.get("author")) or None,
        }
