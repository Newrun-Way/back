

from typing import List, Dict
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from loguru import logger


class DocumentChunker:
    """문서 청킹 클래스"""
    
    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 150,
        separators: List[str] = None
    ):
        """
        Args:
            chunk_size: 청크 크기 (토큰)
            chunk_overlap: 청크 간 겹침 (토큰)
            separators: 구분자 리스트
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ".", "!", "?", " ", ""]
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.separators,
            length_function=len,
        )
        
        logger.info(f"DocumentChunker 초기화: chunk_size={chunk_size}, overlap={chunk_overlap}")
    
    def chunk_text(
        self,
        text: str,
        metadata: Dict = None
    ) -> List[Document]:
        """
        텍스트를 청크로 분할
        
        Args:
            text: 입력 텍스트
            metadata: 메타데이터 (문서명, 섹션 등)
        
        Returns:
            Document 리스트
        """
        if not text or not text.strip():
            logger.warning("빈 텍스트 입력")
            return []
        
        # 메타데이터 기본값
        if metadata is None:
            metadata = {}
        
        # 청크 생성
        chunks = self.text_splitter.create_documents(
            texts=[text],
            metadatas=[metadata]
        )
        
        # 청크 ID 추가
        for i, chunk in enumerate(chunks):
            chunk.metadata['chunk_id'] = i
            chunk.metadata['chunk_size'] = len(chunk.page_content)
        
        logger.info(f"텍스트 청킹 완료: {len(chunks)}개 청크 생성")
        return chunks
    
    def chunk_documents(
        self,
        documents: List[Dict]
    ) -> List[Document]:
        """
        여러 문서를 청크로 분할
        
        Args:
            documents: 문서 리스트 [{"text": str, "metadata": dict}, ...]
        
        Returns:
            Document 리스트
        """
        all_chunks = []
        
        for doc_idx, doc in enumerate(documents):
            text = doc.get("text", "")
            metadata = doc.get("metadata", {})
            metadata['doc_idx'] = doc_idx
            
            chunks = self.chunk_text(text, metadata)
            all_chunks.extend(chunks)
        
        logger.info(f"전체 문서 청킹 완료: {len(documents)}개 문서 → {len(all_chunks)}개 청크")
        return all_chunks
    
    def chunk_with_tables(
        self,
        text: str,
        tables: List[Dict],
        metadata: Dict = None
    ) -> List[Document]:
        """
        텍스트와 표를 함께 청크로 분할
        표는 별도 청크로 생성
        
        Args:
            text: 입력 텍스트
            tables: 표 리스트 [{"summary": str, "rows": [[str]], ...}, ...]
            metadata: 메타데이터
        
        Returns:
            Document 리스트
        """
        if metadata is None:
            metadata = {}
        
        chunks = []
        
        # 1. 일반 텍스트 청킹
        text_chunks = self.chunk_text(text, metadata)
        chunks.extend(text_chunks)
        
        # 2. 표 청킹 (각 표는 별도 청크)
        for table_idx, table in enumerate(tables):
            table_content = self._format_table(table)
            table_metadata = metadata.copy()
            table_metadata['type'] = 'table'
            table_metadata['table_idx'] = table_idx
            table_metadata['table_summary'] = table.get('summary', '')
            
            table_doc = Document(
                page_content=table_content,
                metadata=table_metadata
            )
            chunks.append(table_doc)
        
        logger.info(f"텍스트+표 청킹 완료: 텍스트 {len(text_chunks)}개 + 표 {len(tables)}개")
        return chunks
    
    def _format_table(self, table: Dict) -> str:
        """
        표를 텍스트 형식으로 변환
        
        Args:
            table: 표 데이터
        
        Returns:
            포맷된 텍스트
        """
        lines = []
        
        # 표 요약
        if 'summary' in table:
            lines.append(f"[{table['summary']}]")
            lines.append("")
        
        # 표 내용
        rows = table.get('rows', [])
        if rows:
            # 헤더 (첫 행)
            if len(rows) > 0:
                lines.append(" | ".join(rows[0]))
                lines.append("-" * (len(" | ".join(rows[0]))))
            
            # 데이터 행
            for row in rows[1:]:
                lines.append(" | ".join(row))
        
        return "\n".join(lines)


def test_chunker():
    """청킹 테스트"""
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
    
    # 테스트 텍스트
    text = """
    2024년 디지털정부 발전유공 포상 추진계획
    
    1. 목적
    디지털정부 발전에 기여한 공무원 및 민간인의 노력을 격려하고,
    우수 사례를 발굴하여 확산하기 위함
    
    2. 포상 개요
    - 대상: 공무원, 민간인
    - 규모: 총 50명 내외
    - 시기: 2024년 12월
    """
    
    metadata = {
        "doc_name": "포상_추진계획.hwpx",
        "section": "전체"
    }
    
    chunks = chunker.chunk_text(text, metadata)
    
    print(f"\n=== 청킹 테스트 결과 ===")
    print(f"생성된 청크 수: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"\n[청크 {i+1}]")
        print(f"내용: {chunk.page_content[:100]}...")
        print(f"메타데이터: {chunk.metadata}")


if __name__ == "__main__":
    test_chunker()

