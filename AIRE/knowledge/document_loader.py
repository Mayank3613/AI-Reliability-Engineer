"""
Document Loader — Layer 5.
Loads markdown documents and splits them into overlapping chunks
suitable for embedding and Agent Search ingestion.
"""

import re
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    text: str
    source: str
    heading: str = ""
    chunk_index: int = 0
    char_start: int = 0
    char_end: int = 0
    metadata: dict = field(default_factory=dict)


class DocumentLoader:
    """
    Loads markdown files and chunks them into overlapping segments
    for embedding and retrieval.
    """

    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 100,
        min_chunk_size: int = 100,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def load_and_chunk(self, file_path: str | Path) -> list[DocumentChunk]:
        """Load a markdown file and return overlapping text chunks."""
        path = Path(file_path)
        text = path.read_text(encoding="utf-8")
        return self._chunk_markdown(text, source=path.name)

    def _chunk_markdown(self, text: str, source: str) -> list[DocumentChunk]:
        """
        Smart markdown chunker:
        1. Split on H2/H3 headings first
        2. Further split large sections by paragraph
        3. Apply overlap
        """
        sections = self._split_by_headings(text)
        chunks = []
        chunk_idx = 0

        for heading, content in sections:
            # If section fits in one chunk, keep it whole
            if len(content) <= self.chunk_size:
                if len(content.strip()) >= self.min_chunk_size:
                    chunks.append(DocumentChunk(
                        text=f"{heading}\n{content}".strip() if heading else content.strip(),
                        source=source,
                        heading=heading,
                        chunk_index=chunk_idx,
                        char_start=0,
                        char_end=len(content),
                    ))
                    chunk_idx += 1
            else:
                # Split large sections by paragraph with overlap
                sub_chunks = self._sliding_window(content, source, heading, chunk_idx)
                chunks.extend(sub_chunks)
                chunk_idx += len(sub_chunks)

        logger.debug("Chunked '%s': %d chunks from %d chars", source, len(chunks), len(text))
        return chunks

    def _split_by_headings(self, text: str) -> list[tuple[str, str]]:
        """Split markdown into (heading, content) pairs."""
        pattern = re.compile(r'^(#{1,3}\s+.+)$', re.MULTILINE)
        parts = pattern.split(text)

        sections = []
        if parts[0].strip():
            sections.append(("", parts[0].strip()))

        for i in range(1, len(parts), 2):
            heading = parts[i].strip() if i < len(parts) else ""
            content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if content:
                sections.append((heading, content))

        return sections

    def _sliding_window(
        self, text: str, source: str, heading: str, start_idx: int
    ) -> list[DocumentChunk]:
        """Apply sliding window chunking with overlap."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []
        current = []
        current_len = 0

        for para in paragraphs:
            if current_len + len(para) > self.chunk_size and current:
                chunk_text = "\n\n".join(current)
                if len(chunk_text.strip()) >= self.min_chunk_size:
                    prefix = f"{heading}\n" if heading else ""
                    chunks.append(DocumentChunk(
                        text=(prefix + chunk_text).strip(),
                        source=source,
                        heading=heading,
                        chunk_index=start_idx + len(chunks),
                    ))
                # Overlap: keep last paragraph
                overlap_para = current[-1] if current else ""
                current = [overlap_para, para] if overlap_para else [para]
                current_len = sum(len(p) for p in current)
            else:
                current.append(para)
                current_len += len(para)

        # Last chunk
        if current:
            chunk_text = "\n\n".join(current)
            if len(chunk_text.strip()) >= self.min_chunk_size:
                prefix = f"{heading}\n" if heading else ""
                chunks.append(DocumentChunk(
                    text=(prefix + chunk_text).strip(),
                    source=source,
                    heading=heading,
                    chunk_index=start_idx + len(chunks),
                ))

        return chunks

    def load_directory(self, directory: str | Path) -> dict[str, list[DocumentChunk]]:
        """Load all markdown files from a directory."""
        path = Path(directory)
        result = {}
        for md_file in sorted(path.glob("*.md")):
            try:
                chunks = self.load_and_chunk(md_file)
                result[md_file.name] = chunks
                logger.info("Loaded '%s': %d chunks", md_file.name, len(chunks))
            except Exception as e:
                logger.error("Failed to load '%s': %s", md_file.name, e)
        return result