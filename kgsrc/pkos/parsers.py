"""Multi-modal document parsers for PKOS Ingest Pipeline.

MVP supports: text, markdown, PDF, image (description via LLM), web.
"""

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from .models import ParsedContent


class DocumentParser(ABC):
    """Base parser interface."""

    @abstractmethod
    def parse_file(self, file_path: str) -> ParsedContent:
        pass

    @staticmethod
    def get_parser(source_type: str) -> Optional["DocumentParser"]:
        mapping = {
            "text": TextParser(),
            "markdown": TextParser(),
            "pdf": PDFParser(),
            "image": ImageParser(),
            "screenshot": ImageParser(),
            "web": WebParser(),
            "browser_clip": WebParser(),
        }
        return mapping.get(source_type)


class TextParser(DocumentParser):
    """Parse plain text and Markdown files."""

    FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)

    def parse_file(self, file_path: str) -> ParsedContent:
        path = Path(file_path)
        text = path.read_text(encoding="utf-8")
        return self.parse_text(text)

    def parse_text(self, text: str) -> ParsedContent:
        title = None
        raw_text = text

        match = self.FRONTMATTER_PATTERN.match(text)
        if match:
            frontmatter = match.group(1)
            raw_text = match.group(2).strip()
            for line in frontmatter.split("\n"):
                if line.strip().startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"').strip("'")

        if title is None:
            # Extract first # heading as title
            for line in raw_text.split("\n"):
                stripped = line.strip()
                if stripped.startswith("# "):
                    title = stripped[2:].strip()
                    break

        return ParsedContent(raw_text=raw_text, title=title)


class PDFParser(DocumentParser):
    """Parse PDF files using unstructured (MVP: fallback to filename)."""

    def parse_file(self, file_path: str) -> ParsedContent:
        path = Path(file_path)
        try:
            from unstructured.partition.pdf import partition_pdf
            elements = partition_pdf(filename=str(path))
            raw_text = "\n\n".join(str(el) for el in elements)
            return ParsedContent(raw_text=raw_text, title=path.stem)
        except Exception as e:
            print(f"[PDFParser] unstructured failed: {e}, falling back to filename")
            return ParsedContent(raw_text=f"[PDF: {path.name}]", title=path.stem)


class ImageParser(DocumentParser):
    """Parse image files: store to local storage, generate description placeholder."""

    ALLOWED_TYPES = {"png", "jpg", "jpeg", "webp", "gif"}

    def parse_file(self, file_path: str, storage_dir: str = "./pkos_images") -> ParsedContent:
        path = Path(file_path)
        ext = path.suffix.lower().lstrip(".")
        if ext not in self.ALLOWED_TYPES:
            return ParsedContent(raw_text=f"[Unsupported image: {path.name}]")

        # Copy to storage directory
        storage = Path(storage_dir)
        storage.mkdir(parents=True, exist_ok=True)
        dest = storage / path.name
        import shutil
        shutil.copy2(path, dest)

        # MVP: placeholder description; production uses vision LLM
        image_ref = f"![AI描述：{path.name}]({dest})"
        return ParsedContent(
            raw_text=f"## 图片描述\n\n{image_ref}\n\n",
            title=f"图片: {path.stem}",
            extracted_images=[{"path": str(dest), "filename": path.name}],
        )


class WebParser(DocumentParser):
    """Parse web pages / HTML content."""

    def parse_file(self, file_path: str) -> ParsedContent:
        text = Path(file_path).read_text(encoding="utf-8")
        return self.parse_html(text)

    def parse_html(self, html: str, source_url: Optional[str] = None) -> ParsedContent:
        title = None
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Extract title
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)

            # Extract body text
            body = soup.find("body")
            if body:
                # Remove script/style tags
                for tag in body.find_all(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                raw_text = body.get_text(separator="\n", strip=True)
            else:
                raw_text = soup.get_text(separator="\n", strip=True)

            return ParsedContent(raw_text=raw_text, title=title, source_url=source_url)
        except ImportError:
            print("[WebParser] BeautifulSoup not installed, using regex fallback")
            # Regex fallback
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()
            raw_text = re.sub(r"<[^>]+>", "", html)
            return ParsedContent(raw_text=raw_text, title=title, source_url=source_url)
