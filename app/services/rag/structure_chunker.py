from __future__ import annotations
from typing import Dict, List
from langchain_core.documents import Document
from loguru import logger


class StructureAwareChunker:
    """
    구조 기반 청킹 엔진
    parser.py → result["structure"] 를 기반으로
    장/조/항 구조를 반영한 의미 단위 청킹을 수행한다.
    """

    def __init__(self, max_chunk_size=800, min_chunk_size=200, overlap_size=150):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap_size = overlap_size

    # ----------------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------------
    def chunk_by_structure(
        self, text: str, doc_structure: Dict, base_metadata: Dict
    ) -> List[Document]:
        """
        구조 정보(doc_structure)를 기반으로 텍스트를 장/조/항 단위로 청킹한다.
        """

        if not doc_structure or "structure_map" not in doc_structure:
            logger.warning("구조 정보가 없어 일반 청킹 fallback 필요")
            return self._fallback_chunk(text, base_metadata)

        text_lines = text.split("\n")
        structure_map = doc_structure["structure_map"]

        sections = self._extract_sections(text_lines, structure_map)
        logger.info(f"구조 기반 분할된 섹션 수: {len(sections)}")

        chunks: List[Document] = []

        for s_idx, section in enumerate(sections):
            section_text = "\n".join(section["lines"]).strip()
            if not section_text:
                continue

            metadata = self._build_metadata(section, base_metadata)
            metadata["chunk_index"] = s_idx
            metadata["chunking_strategy"] = "structure"

            doc = Document(page_content=section_text, metadata=metadata)
            chunks.append(doc)

        return chunks

    # ----------------------------------------------------------------------
    # Section extraction
    # ----------------------------------------------------------------------
    def _extract_sections(self, text_lines, structure_map):
        """
        장/조/항 라인에 따라 문서를 의미 단위 sections 리스트로 변환.
        """

        sections = []
        current = {"lines": [], "info": {}}

        for idx, line in enumerate(text_lines):
            info = structure_map.get(idx)

            # 새로운 Article 시작이면 기존 섹션을 저장하고 새 섹션 시작
            if info and info["type"] == "article":
                if current["lines"]:
                    sections.append(current)

                current = {
                    "lines": [line],
                    "info": {
                        "chapter_num": info.get("chapter_num"),
                        "chapter_title": info.get("title", ""),
                        "article_num": info.get("number"),
                        "article_title": info.get("title", ""),
                    },
                }
                continue

            # 기존 섹션 계속 누적
            current["lines"].append(line)

        if current["lines"]:
            sections.append(current)

        return sections

    # ----------------------------------------------------------------------
    # Metadata builder
    # ----------------------------------------------------------------------
    def _build_metadata(self, section, base_metadata):
        info = section["info"]
        meta = dict(base_metadata)

        meta["chapter_num"] = info.get("chapter_num")
        meta["chapter_title"] = info.get("chapter_title")
        meta["article_num"] = info.get("article_num")
        meta["article_title"] = info.get("article_title")

        # hierarchy_path 생성
        parts = []
        if meta.get("chapter_num"):
            title = meta.get("chapter_title", "")
            parts.append(f"제{meta['chapter_num']}장 {title}".strip())
        if meta.get("article_num"):
            title = meta.get("article_title", "")
            parts.append(f"제{meta['article_num']}조 {title}".strip())
        meta["hierarchy_path"] = " > ".join(parts)

        return meta

    # ----------------------------------------------------------------------
    # fallback (general chunking)
    # ----------------------------------------------------------------------
    def _fallback_chunk(self, text: str, metadata: Dict) -> List[Document]:
        """
        구조 정보가 없을 때 일반 청킹 fallback
        (DocumentChunker가 이후 일반 청킹을 맡으므로 여기서는 단일 문단 반환)
        """
        return [Document(page_content=text, metadata=metadata)]
