from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Skill:
    name: str
    description: str
    path: Path
    provider_key: str = "fastapi-startkit"
    body: str = field(default="", repr=False)
    metadata: dict = field(default_factory=dict, repr=False)


class SkillParser:
    """Parses SKILL.md files into :class:`Skill` objects."""

    def parse(self, path: Path, provider_key: str = "fastapi-startkit") -> "Skill | None":
        """Read and parse *path* into a Skill, or ``None`` if it can't be read
        or has no name."""
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None

        meta, body = self.parse_frontmatter(text)
        name = (meta.get("name") or path.parent.name or "").strip()
        if not name:
            return None

        description = (meta.get("description") or "").strip()
        extra = {k: v for k, v in meta.items() if k not in ("name", "description")}
        return Skill(
            name=name,
            description=description,
            path=path,
            provider_key=provider_key,
            body=body.strip(),
            metadata=extra,
        )

    @staticmethod
    def parse_frontmatter(text: str) -> tuple[dict, str]:
        """Split YAML front-matter from the body. Returns (meta_dict, body_str)."""
        lines = text.splitlines(keepends=True)
        if not lines or lines[0].strip() != "---":
            return {}, text

        end_idx = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end_idx = i
                break

        if end_idx is None:
            return {}, text

        fm_text = "".join(lines[1:end_idx])
        body = "".join(lines[end_idx + 1 :])

        try:
            import yaml

            meta = yaml.safe_load(fm_text) or {}
        except ModuleNotFoundError:
            meta = {}
            for line in lines[1:end_idx]:
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip()

        return meta, body
