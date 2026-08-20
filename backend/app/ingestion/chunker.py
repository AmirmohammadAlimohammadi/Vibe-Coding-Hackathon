from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt


ORIGINAL_LINK_RE = re.compile(r"^Original link:\s*(https?://\S+)\s*$", re.MULTILINE)
MARKDOWN_LINK_RE = re.compile(r"!?\[([^\]]*)\]\((https?://[^)]+)\)")
MEDIA_RE = re.compile(r"!?\[([^\]]*)\]\((https?://[^)]+\.(?:png|jpe?g|gif|webp|mp4|mov|mp3|wav))\)", re.IGNORECASE)
DATA_URL_RE = re.compile(r"data:[^\s'\"`)]+", re.IGNORECASE)
PERSIAN_RE = re.compile(r"[\u0600-\u06FF]")
FENCE_RE = re.compile(r"^```([^\r\n]*)\r?\n([\s\S]*?)\r?\n```\s*$")
ALL_LINKS_TITLES = {"all links", "همه لینک‌ها", "تمام لینک‌ها"}
RELATED_READING_MARKERS = ("همچنین بخوانید", "مطالب مرتبط")
NAMESPACE = uuid.UUID("316a0a22-1662-4dda-9f51-5ea7373f65a1")


@dataclass(slots=True)
class Section:
    index: int
    title: str
    heading_path: list[str]
    body: str


@dataclass(slots=True)
class Chunk:
    point_id: str
    document_id: str
    content: str
    embedding_text: str
    source_path: str
    source_url: str
    source_url_derived: bool
    document_title: str
    heading_path: list[str]
    section_title: str
    product_family: str
    service: str | None
    category: str | None
    doc_type: str
    topic: str
    language: str
    content_type: str
    code_languages: list[str]
    has_code: bool
    chunk_index: int
    section_chunk_index: int
    token_count: int
    previous_chunk_id: str | None
    next_chunk_id: str | None
    related_urls: list[str]
    media_urls: list[str]
    content_hash: str
    ingestion_version: str

    def payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("point_id")
        return payload


class MarkdownChunker:
    def __init__(
        self,
        target_tokens: int = 350,
        max_tokens: int = 500,
        min_tokens: int = 80,
        overlap_tokens: int = 50,
        ingestion_version: str = "1",
    ) -> None:
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens
        self.overlap_tokens = overlap_tokens
        self.ingestion_version = ingestion_version
        self.markdown = MarkdownIt("commonmark")
        self.warnings: list[str] = []

    def chunk_directory(self, docs_dir: Path) -> list[Chunk]:
        chunks: list[Chunk] = []
        for path in sorted(docs_dir.rglob("*.md")):
            chunks.extend(self.chunk_file(path, docs_dir))
        return chunks

    def chunk_file(self, path: Path, docs_dir: Path) -> list[Chunk]:
        raw = path.read_text(encoding="utf-8-sig")
        source_path = path.relative_to(docs_dir).as_posix()
        source_match = ORIGINAL_LINK_RE.search(raw)
        source_url_derived = source_match is None
        source_url = (
            source_match.group(1)
            if source_match
            else f"https://docs.liara.ir/{source_path.removesuffix('.md')}/"
        )
        related_urls = sorted(set(self._extract_links(raw)))
        media_urls = sorted(set(match.group(2) for match in MEDIA_RE.finditer(raw)))
        sections, document_title = self._extract_sections(raw, source_path)
        taxonomy = self._taxonomy(source_path)
        document_id = hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:24]
        chunks: list[Chunk] = []

        for section in sections:
            clean_body = self._clean_body(section.body)
            if not clean_body.strip():
                continue
            pieces = self._split_section(clean_body)
            for section_chunk_index, content in enumerate(pieces):
                embedding_text = self._embedding_text(
                    taxonomy=taxonomy,
                    document_title=document_title,
                    heading_path=section.heading_path,
                    content=content,
                )
                code_languages = sorted(
                    {
                        match.group(1).strip().lower()
                        for match in re.finditer(r"^```([^\r\n]*)", content, re.MULTILINE)
                        if match.group(1).strip()
                    }
                )
                has_code = "```" in content
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                stable_key = f"{source_path}|{section.index}|{section_chunk_index}"
                point_id = str(uuid.uuid5(NAMESPACE, stable_key))
                chunks.append(
                    Chunk(
                        point_id=point_id,
                        document_id=document_id,
                        content=content,
                        embedding_text=embedding_text,
                        source_path=source_path,
                        source_url=source_url,
                        source_url_derived=source_url_derived,
                        document_title=document_title,
                        heading_path=section.heading_path,
                        section_title=section.title,
                        product_family=taxonomy["product_family"],
                        service=taxonomy["service"],
                        category=taxonomy["category"],
                        doc_type=taxonomy["doc_type"],
                        topic=taxonomy["topic"],
                        language=self._language(content),
                        content_type=self._content_type(content),
                        code_languages=code_languages,
                        has_code=has_code,
                        chunk_index=len(chunks),
                        section_chunk_index=section_chunk_index,
                        token_count=self.estimate_tokens(embedding_text),
                        previous_chunk_id=None,
                        next_chunk_id=None,
                        related_urls=related_urls,
                        media_urls=media_urls,
                        content_hash=content_hash,
                        ingestion_version=self.ingestion_version,
                    )
                )

        for index, chunk in enumerate(chunks):
            chunk.previous_chunk_id = chunks[index - 1].point_id if index else None
            chunk.next_chunk_id = chunks[index + 1].point_id if index + 1 < len(chunks) else None
        return chunks

    def _extract_sections(self, raw: str, source_path: str) -> tuple[list[Section], str]:
        lines = raw.splitlines()
        tokens = self.markdown.parse(raw)
        headings: list[tuple[int, int, str]] = []
        for index, token in enumerate(tokens):
            if token.type != "heading_open" or token.map is None:
                continue
            title = tokens[index + 1].content.strip() if index + 1 < len(tokens) else ""
            headings.append((token.map[0], int(token.tag[1]), title))

        if not headings:
            fallback_title = Path(source_path).stem.replace("-", " ")
            self.warnings.append(f"{source_path}: no Markdown heading; using filename")
            return [Section(0, fallback_title, [fallback_title], raw)], fallback_title

        first_h1 = next((heading for heading in headings if heading[1] == 1), headings[0])
        document_title = first_h1[2] or Path(source_path).stem.replace("-", " ")
        stack: list[tuple[int, str]] = []
        sections: list[Section] = []

        for index, (line_number, level, title) in enumerate(headings):
            end_line = headings[index + 1][0] if index + 1 < len(headings) else len(lines)
            body = "\n".join(lines[line_number + 1 : end_line]).strip()
            normalized_title = title.strip().casefold()
            if normalized_title in ALL_LINKS_TITLES:
                continue
            if any(marker in title for marker in RELATED_READING_MARKERS):
                continue

            effective_level = 2 if level == 1 and title != document_title else level
            stack = [(stack_level, value) for stack_level, value in stack if stack_level < effective_level]
            if title != document_title or not stack:
                stack.append((effective_level, title))
            heading_path = [value for _, value in stack if value]
            if document_title not in heading_path:
                heading_path.insert(0, document_title)
            sections.append(Section(index=index, title=title, heading_path=heading_path, body=body))

        return sections, document_title

    def _split_section(self, body: str) -> list[str]:
        blocks = self._top_level_blocks(body)
        atomic_blocks: list[str] = []
        for block in blocks:
            if self.estimate_tokens(block) <= self.max_tokens:
                atomic_blocks.append(block)
            else:
                atomic_blocks.extend(self._split_oversized_block(block))

        packed: list[str] = []
        current: list[str] = []
        current_tokens = 0
        for block in atomic_blocks:
            block_tokens = self.estimate_tokens(block)
            if current and current_tokens + block_tokens > self.target_tokens:
                packed.append("\n\n".join(current).strip())
                overlap = self._overlap_block(current[-1])
                current = [overlap] if overlap else []
                current_tokens = self.estimate_tokens(overlap) if overlap else 0
            current.append(block)
            current_tokens += block_tokens
        if current:
            packed.append("\n\n".join(current).strip())

        if len(packed) > 1 and self.estimate_tokens(packed[-1]) < self.min_tokens:
            combined = f"{packed[-2]}\n\n{packed[-1]}"
            if self.estimate_tokens(combined) <= self.max_tokens:
                packed[-2:] = [combined]
        return [piece for piece in packed if piece.strip()]

    def _top_level_blocks(self, body: str) -> list[str]:
        lines = body.splitlines()
        tokens = self.markdown.parse(body)
        ranges: list[tuple[int, int]] = []
        for token in tokens:
            if token.level != 0 or token.map is None:
                continue
            if token.type.endswith("_close") or token.type == "heading_open":
                continue
            candidate = (token.map[0], token.map[1])
            if candidate not in ranges:
                ranges.append(candidate)
        if not ranges:
            return [body.strip()] if body.strip() else []
        return ["\n".join(lines[start:end]).strip() for start, end in ranges if start < end]

    def _split_oversized_block(self, block: str) -> list[str]:
        fence_match = FENCE_RE.match(block)
        if fence_match:
            language, code = fence_match.groups()
            lines = code.splitlines()
            pieces: list[str] = []
            current: list[str] = []
            for line in lines:
                candidate = "\n".join(current + [line])
                wrapped = f"```{language}\n{candidate}\n```"
                if current and self.estimate_tokens(wrapped) > self.max_tokens:
                    pieces.append(f"```{language}\n{'\n'.join(current)}\n```")
                    current = []
                current.append(line)
            if current:
                pieces.append(f"```{language}\n{'\n'.join(current)}\n```")
            return pieces

        sentences = re.split(r"(?<=[.!?؟؛])\s+|\n\s*\n", block)
        pieces: list[str] = []
        current: list[str] = []
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if self.estimate_tokens(sentence) > self.max_tokens:
                words = sentence.split()
                for word in words:
                    candidate = " ".join(current + [word])
                    if current and self.estimate_tokens(candidate) > self.max_tokens:
                        pieces.append(" ".join(current))
                        current = []
                    current.append(word)
                continue
            candidate = " ".join(current + [sentence])
            if current and self.estimate_tokens(candidate) > self.max_tokens:
                pieces.append(" ".join(current))
                current = []
            current.append(sentence)
        if current:
            pieces.append(" ".join(current))
        return pieces

    def _overlap_block(self, block: str) -> str:
        if "```" in block or self.estimate_tokens(block) > self.overlap_tokens:
            return ""
        return block

    def _clean_body(self, body: str) -> str:
        body = ORIGINAL_LINK_RE.sub("", body)
        body = re.sub(r"^>\s*همچنین بخوانید:.*$", "", body, flags=re.MULTILINE)
        body = MEDIA_RE.sub(lambda match: match.group(1), body)
        body = DATA_URL_RE.sub("[embedded media omitted]", body)
        return re.sub(r"\n{3,}", "\n\n", body).strip()

    def _embedding_text(
        self,
        taxonomy: dict[str, str | None],
        document_title: str,
        heading_path: list[str],
        content: str,
    ) -> str:
        plain_content = MARKDOWN_LINK_RE.sub(lambda match: match.group(1), content)
        breadcrumb = " > ".join(heading_path)
        service = f" > {taxonomy['service']}" if taxonomy["service"] else ""
        context = (
            f"Product: {taxonomy['product_family']}{service}\n"
            f"Document: {document_title}\n"
            f"Section: {breadcrumb}\n"
        )
        return f"title: {document_title} | text: {context}{plain_content}".strip()

    def _taxonomy(self, source_path: str) -> dict[str, str | None]:
        parts = Path(source_path).with_suffix("").parts
        product_family = parts[0]
        service = parts[1] if len(parts) > 2 else None
        topic = parts[-1]
        category_markers = {
            "how-tos",
            "details",
            "api",
            "cookbook",
            "references",
            "foundations",
            "getting-started",
            "fix-common-errors",
        }
        category = next((part for part in parts if part in category_markers), None)
        if "fix-common-errors" in parts:
            doc_type = "troubleshooting"
        elif "how-tos" in parts:
            doc_type = "how-to"
        elif "api" in parts or product_family == "references":
            doc_type = "reference"
        elif "cookbook" in parts:
            doc_type = "cookbook"
        elif topic in {"quick-start", "quick-setup", "getting-started"}:
            doc_type = "getting-started"
        elif topic == "about":
            doc_type = "overview"
        elif topic == "choose-version":
            doc_type = "version-guide"
        else:
            doc_type = "guide"
        return {
            "product_family": product_family,
            "service": service,
            "category": category,
            "doc_type": doc_type,
            "topic": topic,
        }

    def _extract_links(self, raw: str) -> list[str]:
        return [match.group(2) for match in MARKDOWN_LINK_RE.finditer(raw)]

    def _language(self, content: str) -> str:
        persian_count = len(PERSIAN_RE.findall(content))
        ascii_letters = len(re.findall(r"[A-Za-z]", content))
        if persian_count and ascii_letters:
            return "fa-en"
        if persian_count:
            return "fa"
        return "en"

    def _content_type(self, content: str) -> str:
        has_code = "```" in content
        has_steps = bool(re.search(r"(?m)^\s*(?:[-*]|\d+[.)]|[۰-۹]+[.)])\s+", content))
        if has_code and has_steps:
            return "mixed"
        if has_code:
            return "code"
        if has_steps:
            return "procedure"
        return "prose"

    @staticmethod
    def estimate_tokens(text: str) -> int:
        persian_chars = len(PERSIAN_RE.findall(text))
        without_persian = PERSIAN_RE.sub("", text)
        latin_words = len(re.findall(r"[A-Za-z0-9_]+", without_persian))
        punctuation = len(re.findall(r"[^\w\s]", without_persian))
        return max(1, (persian_chars + 1) // 2 + latin_words + punctuation // 2)
