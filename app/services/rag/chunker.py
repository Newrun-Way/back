# app/services/rag/chunker.py
from __future__ import annotations
from typing import List, Dict, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from loguru import logger

from app.core.config import get_settings
from app.services.rag.structure_chunker import StructureAwareChunker


class DocumentChunker:
    """
    백엔드 공용 청킹 클래스

    - 일반 청킹: RecursiveCharacterTextSplitter 사용
    - 구조 청킹: StructureAwareChunker 사용 (문서 전체 + doc_structure 기반)
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        separators: Optional[List[str]] = None,
    ):
        settings = get_settings()

        self.chunk_size = chunk_size or getattr(settings, "CHUNK_SIZE", 800)
        self.chunk_overlap = chunk_overlap or getattr(settings, "CHUNK_OVERLAP", 150)
        self.separators = separators or getattr(
            settings,
            "SEPARATORS",
            ["\n\n", "\n", ".", "!", "?", " ", ""],
        )

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.separators,
            length_function=len,
        )

        # 구조 기반 청커
        self.structure_chunker = StructureAwareChunker(
            max_chunk_size=self.chunk_size,
            min_chunk_size=max(100, int(self.chunk_size * 0.25)),
            overlap_size=self.chunk_overlap,
        )

        logger.info(
            f"DocumentChunker 초기화: size={self.chunk_size}, overlap={self.chunk_overlap}"
        )

    # ------------------------------------------------------------------
    # 일반 청킹 (구조 정보 없는 경우)
    # ------------------------------------------------------------------
    def chunk_text(
        self,
        text: str,
        metadata: Dict | None = None
    ) -> List[Document]:
        """
        일반 텍스트 청킹 (구조 정보 없음)
        """
        if not text or not text.strip():
            logger.warning("DocumentChunker.chunk_text: 빈 텍스트 입력")
            return []

        metadata = metadata or {}

        docs = self.text_splitter.create_documents(
            texts=[text],
            metadatas=[metadata],
        )

        for idx, ch in enumerate(docs):
            ch.metadata["chunk_id"] = idx
            ch.metadata["chunk_size"] = len(ch.page_content)
            ch.metadata.setdefault("chunking_strategy", "general")

        logger.info(f"일반 청킹 완료: {len(docs)}개 생성")
        return docs

    # ------------------------------------------------------------------
    # 구조 기반 청킹 (문서 전체 + doc_structure)
    # ------------------------------------------------------------------
    def chunk_text_with_structure(
        self,
        full_text: str,
        doc_structure: Dict,
        metadata: Dict | None = None
    ) -> List[Document]:
        """
        parser.py에서 생성된 doc_structure를 사용하는 구조 기반 청킹.
        (문서 전체 텍스트를 한 번에 받아 처리)
        """
        if not full_text or not full_text.strip():
            logger.warning("DocumentChunker.chunk_text_with_structure: 빈 텍스트 입력")
            return []

        metadata = metadata or {}

        chunks = self.structure_chunker.chunk_by_structure(
            full_text,
            doc_structure,
            metadata,
        )

        # chunk_id / chunk_size 보정
        for idx, ch in enumerate(chunks):
            ch.metadata["chunk_id"] = idx
            ch.metadata["chunk_size"] = len(ch.page_content)
            ch.metadata.setdefault("chunking_strategy", "structure")

        logger.info(f"구조 기반 청킹 완료: {len(chunks)}개 생성")
        return chunks

    # ------------------------------------------------------------------
    # 여러 문서 청킹 (현재는 일반 청킹 기준)
    # ------------------------------------------------------------------
    def chunk_documents(self, documents: List[Dict]) -> List[Document]:
        """
        여러 문서를 일반 청킹으로 분할
        Args: [{"text": str, "metadata": dict}, ...]
        """
        all_chunks: List[Document] = []

        for doc_idx, doc in enumerate(documents):
            text = doc.get("text", "")
            metadata = doc.get("metadata", {}) or {}
            metadata["doc_idx"] = doc_idx

            chunks = self.chunk_text(text, metadata)
            all_chunks.extend(chunks)

        logger.info(
            f"전체 문서 청킹 완료: {len(documents)}개 문서 → {len(all_chunks)}개 청크"
        )
        return all_chunks

    # ------------------------------------------------------------------
    # 텍스트 + 표 청킹
    # ------------------------------------------------------------------
    def chunk_with_tables(
        self,
        text: str,
        tables: List[Dict],
        metadata: Dict | None = None
    ) -> List[Document]:
        """
        텍스트는 청킹(구조/일반), 표는 별도 청크로 생성
        현재는 내부에서 일반 chunk_text를 사용.
        """
        metadata = metadata or {}
        chunks: List[Document] = []

        # 1) 텍스트
        text_chunks = self.chunk_text(text, metadata)
        chunks.extend(text_chunks)

        # 2) 표 처리 (각 표는 별도 청크)
        for t_idx, table in enumerate(tables):
            table_content = self._format_table(table)
            t_meta = metadata.copy()
            t_meta["type"] = "table"
            t_meta["table_idx"] = t_idx
            t_meta["table_summary"] = table.get("summary", "")
            t_meta.setdefault("chunking_strategy", "table")

            t_doc = Document(
                page_content=table_content,
                metadata=t_meta,
            )
            chunks.append(t_doc)

        logger.info(
            f"텍스트+표 청킹 완료: 텍스트 {len(text_chunks)}개 + 표 {len(tables)}개"
        )
        return chunks

    # ------------------------------------------------------------------
    # 내부 util
    # ------------------------------------------------------------------
    def _format_table(self, table: Dict) -> str:
        """
        표를 텍스트 형식으로 변환
        """
        lines: List[str] = []

        if "summary" in table:
            lines.append(f"[{table['summary']}]")
            lines.append("")

        rows = table.get("rows", [])
        if rows:
            header = " | ".join(rows[0])
            lines.append(header)
            lines.append("-" * len(header))

            for row in rows[1:]:
                lines.append(" | ".join(row))

        return "\n".join(lines)
