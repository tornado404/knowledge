"""Vault manager — write and read structured Markdown documents."""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional


class VaultManager:
    """Manage PKOS Vault: structured Markdown with YAML frontmatter."""

    def __init__(self, vault_dir: str = "./kgsrc/pkos/vault"):
        self.vault_dir = Path(vault_dir)
        self.vault_dir.mkdir(parents=True, exist_ok=True)

    def _slugify(self, text: str) -> str:
        """Convert text to URL-safe slug."""
        text = re.sub(r"[^\w\s一-鿿\-/]", "", text)
        text = re.sub(r"[\s/]+", "-", text.strip())
        return text

    def _build_frontmatter(
        self,
        title: str,
        source_type: str,
        summary: str = "",
        identities: List[str] = None,
        tags: List[str] = None,
        source_url: Optional[str] = None,
        topic: str = "",
    ) -> str:
        lines = [
            "---",
            f'title: "{title}"',
            f"date: {datetime.now().isoformat()}",
            f'source_type: "{source_type}"',
        ]
        if source_url:
            lines.append(f'source_url: "{source_url}"')
        if identities:
            lines.append(f"identities: {identities}")
        if tags:
            lines.append(f"tags: {tags}")
        if summary:
            lines.append(f'summary: "{summary}"')
        if topic:
            lines.append(f'topic: "{topic}"')
        lines.append("---")
        return "\n".join(lines)

    def write_document(
        self,
        topic: str,
        title: str,
        content: str,
        source_type: str,
        summary: str = "",
        identities: List[str] = None,
        tags: List[str] = None,
        source_url: Optional[str] = None,
        date: Optional[str] = None,
    ) -> Optional[Path]:
        """Write a document to the Vault.

        Returns:
            Path to the written file, or None on failure.
        """
        try:
            topic_dir = self.vault_dir / self._slugify(topic)
            topic_dir.mkdir(parents=True, exist_ok=True)

            date_str = date or datetime.now().strftime("%Y-%m-%d")
            slug = self._slugify(title)
            filename = f"{date_str}-{slug}.md"
            file_path = topic_dir / filename

            frontmatter = self._build_frontmatter(
                title=title,
                source_type=source_type,
                summary=summary,
                identities=identities or [],
                tags=tags or [],
                source_url=source_url,
                topic=topic,
            )

            doc_content = f"{frontmatter}\n\n# {title}\n\n"
            if source_url:
                doc_content += f"> **来源**：[原文链接]({source_url})\n> **归档时间**：{date_str}\n\n"
            doc_content += content
            doc_content += "\n\n---\n*本内容由 PKOS Ingest Pipeline 自动归档*\n"

            file_path.write_text(doc_content, encoding="utf-8")
            return file_path
        except Exception as e:
            print(f"[VaultManager] write failed: {e}")
            return None

    def read_document(self, file_path: str) -> dict:
        """Read a Vault document, returning frontmatter and content."""
        path = Path(file_path)
        text = path.read_text(encoding="utf-8")

        frontmatter = {}
        content = text

        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                import yaml
                try:
                    frontmatter = yaml.safe_load(parts[1])
                except Exception:
                    frontmatter = {}
                content = parts[2].strip()

        return {
            "path": str(path),
            "frontmatter": frontmatter,
            "content": content,
        }

    def list_topics(self) -> List[str]:
        """List all topic directories."""
        return [d.name for d in self.vault_dir.iterdir() if d.is_dir()]

    def list_documents(self, topic: Optional[str] = None) -> List[Path]:
        """List all Markdown documents, optionally filtered by topic."""
        if topic:
            target = self.vault_dir / self._slugify(topic)
            if target.exists():
                return list(target.glob("*.md"))
            return []
        return list(self.vault_dir.rglob("*.md"))
