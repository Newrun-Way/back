# app/services/rag/structure_chunker.py
"""
구조 우선 청킹 모듈
장/조/항 경계를 고려한 의미 단위 청킹
"""

import re
from typing import List, Dict, Tuple
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class StructureAwareChunker:
    """구조 우선 청킹 클래스"""
    
    def __init__(
        self,
        max_chunk_size: int | None = None,
        min_chunk_size: int = 200,
        overlap_size: int | None = None,
    ):
        """
        Args:
            max_chunk_size: 최대 청크 크기
            min_chunk_size: 최소 청크 크기
            overlap_size: 청크 간 겹침 크기
        """
        self.max_chunk_size = max_chunk_size or settings.CHUNK_SIZE
        self.min_chunk_size = min_chunk_size
        self.overlap_size = overlap_size or settings.CHUNK_OVERLAP
        
        # 정규식 패턴
        self.patterns = {
            'chapter': re.compile(r'^제\s*(\d+)\s*장\s+(.+)$', re.MULTILINE),
            'article': re.compile(r'^제\s*(\d+)\s*조\s*(?:\((.+?)\))?(.*)$', re.MULTILINE),
            'paragraph': re.compile(r'^([①②③④⑤⑥⑦⑧⑨⑩]|\d+\))\s*(.*)$', re.MULTILINE),
            'subparagraph': re.compile(r'^([가나다라마바사아자차카타파하])\.\s+(.*)$', re.MULTILINE)
        }
        
        # 일반 청킹용 text splitter (fallback용)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_chunk_size,
            chunk_overlap=overlap_size,
            separators=getattr(
                settings, "SEPARATORS", ["\n\n", "\n", ".", "!", "?", " ", ""],
            ),
            length_function=len
        )
        
        logger.info(f"StructureAwareChunker 초기화: max={max_chunk_size}, min={min_chunk_size}")
    
    def parse_document_structure(self, text: str) -> List[Dict]:
        """
        문서 구조 파싱
        
        Args:
            text: 전체 문서 텍스트
        
        Returns:
            구조화된 섹션 리스트
                [
                    {
                        "type": "article",  # chapter, article, paragraph
                        "number": "15",
                        "title": "급여의 계산",
                        "chapter_number": "3",
                        "chapter_title": "급여 및 수당",
                        "start": 1234,  # 시작 위치
                        "end": 2345,    # 끝 위치
                        "text": "제15조 (급여의 계산) ..."
                    },
                    ...
                ]
        """
        sections = []
        lines = text.split('\n')
        
        current_chapter = None
        current_chapter_title = ""
        current_article = None
        current_article_title = ""
        
        position = 0  # 현재 위치 추적
        
        for line_idx, line in enumerate(lines):
            line_stripped = line.strip()
            line_length = len(line) + 1  # +1 for newline
            
            if not line_stripped:
                position += line_length
                continue
            
            # 장(Chapter) 감지
            chapter_match = self.patterns['chapter'].match(line_stripped)
            if chapter_match:
                current_chapter = chapter_match.group(1)
                current_chapter_title = chapter_match.group(2).strip()
                
                sections.append({
                    "type": "chapter",
                    "number": current_chapter,
                    "title": current_chapter_title,
                    "chapter_number": current_chapter,
                    "chapter_title": current_chapter_title,
                    "start": position,
                    "end": position + line_length,
                    "text": line_stripped
                })
                
                position += line_length
                continue
            
            # 조(Article) 감지
            article_match = self.patterns['article'].match(line_stripped)
            if article_match:
                current_article = article_match.group(1)
                current_article_title = article_match.group(2).strip() if article_match.group(2) else ''
                
                # 이전 조의 끝 위치 업데이트
                if sections and sections[-1]["type"] == "article":
                    sections[-1]["end"] = position
                
                sections.append({
                    "type": "article",
                    "number": current_article,
                    "title": current_article_title,
                    "chapter_number": current_chapter or "",
                    "chapter_title": current_chapter_title,
                    "article_number": current_article,
                    "article_title": current_article_title,
                    "start": position,
                    "end": len(text),  # 임시로 문서 끝까지
                    "text": ""  # 나중에 채움
                })
            
            position += line_length
        
        # 각 조의 텍스트 추출
        for i, section in enumerate(sections):
            if section["type"] == "article":
                start = section["start"]
                end = sections[i+1]["start"] if i+1 < len(sections) else len(text)
                section["end"] = end
                section["text"] = text[start:end].strip()
        
        logger.info(f"문서 구조 파싱 완료: {len(sections)}개 섹션")
        return sections
    
    def chunk_by_structure(
        self,
        text: str,
        metadata: Dict = None
    ) -> List[Document]:
        """
        구조 기반 청킹
        
        전략:
        1. 조(Article) 단위로 먼저 분할
        2. 조가 max_chunk_size보다 크면 항(Paragraph) 단위로 분할
        3. 항도 크면 일반 청킹 적용
        4. 조가 min_chunk_size보다 작으면 다음 조와 병합
        5. 구조가 없으면 일반 청킹으로 fallback
        
        Args:
            text: 입력 텍스트
            metadata: 메타데이터
        
        Returns:
            Document 리스트
        """
        if metadata is None:
            metadata = {}
        
        # 문서 구조 파싱
        sections = self.parse_document_structure(text)
        
        # 조(Article) 단위로 청킹
        chunks = []
        article_sections = [s for s in sections if s["type"] == "article"]
        
        # 구조가 없으면 일반 청킹으로 fallback
        if not article_sections:
            logger.warning(f"문서 구조를 찾을 수 없습니다. 일반 청킹으로 전환합니다.")
            return self._fallback_to_general_chunking(text, metadata)
        
        i = 0
        while i < len(article_sections):
            section = article_sections[i]
            section_text = section["text"]
            section_len = len(section_text)
            
            # Case 1: 조가 적절한 크기 (min_chunk_size <= len < max_chunk_size)
            if self.min_chunk_size <= section_len < self.max_chunk_size:
                chunk = self._create_chunk(section_text, section, metadata, len(chunks))
                chunks.append(chunk)
                i += 1
            
            # Case 2: 조가 너무 큼 (len >= max_chunk_size)
            elif section_len >= self.max_chunk_size:
                # 항(Paragraph) 단위로 분할 시도
                para_chunks = self._chunk_by_paragraphs(section_text, section, metadata, len(chunks))
                chunks.extend(para_chunks)
                i += 1
            
            # Case 3: 조가 너무 작음 (len < min_chunk_size)
            else:
                # 다음 조와 병합 시도
                merged_text = section_text
                merged_sections = [section]
                j = i + 1
                
                while j < len(article_sections) and len(merged_text) < self.min_chunk_size:
                    next_section = article_sections[j]
                    if len(merged_text) + len(next_section["text"]) < self.max_chunk_size:
                        merged_text += "\n\n" + next_section["text"]
                        merged_sections.append(next_section)
                        j += 1
                    else:
                        break
                
                # 병합된 청크 생성
                if merged_sections:
                    # 첫 번째 섹션의 구조 정보 사용
                    chunk = self._create_chunk(merged_text, merged_sections[0], metadata, len(chunks))
                    chunks.append(chunk)
                
                i = j
        
        # Overlap 처리
        chunks_with_overlap = self._add_overlap(chunks, text)
        
        logger.info(f"구조 기반 청킹 완료: {len(chunks_with_overlap)}개 청크")
        return chunks_with_overlap
    
    def _chunk_by_paragraphs(
        self,
        article_text: str,
        article_section: Dict,
        metadata: Dict,
        chunk_start_idx: int
    ) -> List[Document]:
        """
        항(Paragraph) 단위로 분할
        
        Args:
            article_text: 조 텍스트
            article_section: 조 섹션 정보
            metadata: 메타데이터
            chunk_start_idx: 청크 시작 인덱스
        
        Returns:
            Document 리스트
        """
        chunks = []
        
        # 항 패턴으로 분할
        lines = article_text.split('\n')
        current_para_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            
            # 항 시작 감지
            para_match = self.patterns['paragraph'].match(line_stripped)
            if para_match and current_para_lines:
                # 이전 항을 청크로 저장
                para_text = '\n'.join(current_para_lines)
                if len(para_text) >= self.min_chunk_size or not chunks:
                    chunk = self._create_chunk(para_text, article_section, metadata, chunk_start_idx + len(chunks))
                    chunks.append(chunk)
                current_para_lines = [line]
            else:
                current_para_lines.append(line)
        
        # 마지막 항 처리
        if current_para_lines:
            para_text = '\n'.join(current_para_lines)
            if len(para_text) >= self.min_chunk_size or not chunks:
                chunk = self._create_chunk(para_text, article_section, metadata, chunk_start_idx + len(chunks))
                chunks.append(chunk)
        
        # 여전히 청크가 없으면 전체를 하나의 청크로
        if not chunks:
            chunk = self._create_chunk(article_text, article_section, metadata, chunk_start_idx)
            chunks = [chunk]
        
        return chunks
    
    def _create_chunk(
        self,
        text: str,
        section: Dict,
        metadata: Dict,
        chunk_index: int
    ) -> Document:
        """
        청크 Document 생성
        
        Args:
            text: 청크 텍스트
            section: 섹션 정보
            metadata: 기본 메타데이터
            chunk_index: 청크 인덱스
        
        Returns:
            Document
        """
        chunk_metadata = metadata.copy()
        chunk_metadata.update({
            'chunk_index': chunk_index,
            'chunk_size': len(text),
            'chapter_number': section.get('chapter_number', ''),
            'chapter_title': section.get('chapter_title', ''),
            'article_number': section.get('article_number', ''),
            'article_title': section.get('article_title', ''),
            'hierarchy_path': self._build_hierarchy_path(section)
        })
        
        return Document(page_content=text, metadata=chunk_metadata)
    
    def _build_hierarchy_path(self, section: Dict) -> str:
        """
        계층 경로 생성
        
        Args:
            section: 섹션 정보
        
        Returns:
            계층 경로 문자열 (예: "제3장 급여 및 수당 > 제15조 (급여의 계산)")
        """
        parts = []
        
        chapter_num = section.get('chapter_number')
        chapter_title = section.get('chapter_title')
        if chapter_num:
            if chapter_title:
                parts.append(f"제{chapter_num}장 {chapter_title}")
            else:
                parts.append(f"제{chapter_num}장")
        
        article_num = section.get('article_number')
        article_title = section.get('article_title')
        if article_num:
            if article_title:
                parts.append(f"제{article_num}조 ({article_title})")
            else:
                parts.append(f"제{article_num}조")
        
        return " > ".join(parts) if parts else ""
    
    def _add_overlap(
        self,
        chunks: List[Document],
        full_text: str
    ) -> List[Document]:
        """
        청크 간 overlap 추가
        
        Args:
            chunks: 청크 리스트
            full_text: 전체 텍스트
        
        Returns:
            Overlap이 추가된 청크 리스트
        """
        if len(chunks) <= 1 or self.overlap_size == 0:
            return chunks
        
        overlapped_chunks = []
        
        for i, chunk in enumerate(chunks):
            chunk_text = chunk.page_content
            
            # 이전 청크의 마지막 부분 추가
            if i > 0:
                prev_chunk = chunks[i-1]
                prev_text = prev_chunk.page_content
                overlap_text = prev_text[-self.overlap_size:] if len(prev_text) > self.overlap_size else prev_text
                chunk_text = overlap_text + "\n\n" + chunk_text
            
            # 새 Document 생성
            overlapped_chunk = Document(
                page_content=chunk_text,
                metadata=chunk.metadata.copy()
            )
            overlapped_chunks.append(overlapped_chunk)
        
        return overlapped_chunks
    
    def _fallback_to_general_chunking(
        self,
        text: str,
        metadata: Dict
    ) -> List[Document]:
        """
        구조가 없는 문서에 대한 일반 청킹 fallback
        
        Args:
            text: 입력 텍스트
            metadata: 메타데이터
        
        Returns:
            Document 리스트
        """
        logger.info("일반 청킹 적용 중...")
        
        # RecursiveCharacterTextSplitter로 청킹
        chunks = self.text_splitter.create_documents(
            texts=[text],
            metadatas=[metadata]
        )
        
        # 청크 인덱스 추가
        for i, chunk in enumerate(chunks):
            chunk.metadata['chunk_index'] = i
            chunk.metadata['chunk_size'] = len(chunk.page_content)
            # 구조 정보는 비어있음
            chunk.metadata['chapter_number'] = ""
            chunk.metadata['chapter_title'] = ""
            chunk.metadata['article_number'] = ""
            chunk.metadata['article_title'] = ""
            chunk.metadata['hierarchy_path'] = ""
            chunk.metadata['chunking_strategy'] = 'general'  # 일반 청킹임을 표시
        
        logger.info(f"일반 청킹 완료: {len(chunks)}개 청크")
        return chunks


def test_structure_chunker():
    """StructureAwareChunker 테스트"""
    
    # 테스트 텍스트
    test_text = """제3장 급여 및 수당

제15조 (급여의 계산) ① 직원의 월 급여는 기본급과 각종 수당을 합산하여 지급한다. ② 기본급은 직급별로 다음 표와 같이 정한다.

[표: 직급별 기본급 및 수당]
직급 | 기본급 | 직책수당 | 합계
과장 | 3,500,000원 | 300,000원 | 3,800,000원
차장 | 4,200,000원 | 500,000원 | 4,700,000원
부장 | 5,000,000원 | 700,000원 | 5,700,000원

③ 기본급은 매년 1월 1일 기준으로 조정할 수 있다. ④ 조정 비율은 전년도 물가상승률과 경영실적을 고려하여 이사회에서 결정한다.

제16조 (수당의 종류) ① 직원에게 지급하는 수당의 종류는 다음 각 호와 같다.
1. 직책수당: 과장급 이상 직원에게 지급
2. 야간근무수당: 22시 이후 근무 시 시간당 15,000원
3. 주말근무수당: 토요일 또는 일요일 근무 시 시간당 20,000원
4. 자격수당: 업무 관련 국가자격증 소지자에게 월 50,000원

② 수당은 매월 급여일에 기본급과 함께 지급한다. ③ 수당의 종류와 금액은 경영상황에 따라 조정할 수 있다.

제17조 (급여의 지급일) ① 급여는 매월 25일에 지급한다. ② 지급일이 토요일 또는 공휴일인 경우 그 전일에 지급한다."""
    
    chunker = StructureAwareChunker(
        max_chunk_size=800,
        min_chunk_size=200,
        overlap_size=100
    )
    
    print("\n=== 구조 우선 청킹 테스트 ===")
    
    # 구조 파싱 테스트
    print("\n1. 문서 구조 파싱")
    sections = chunker.parse_document_structure(test_text)
    print(f"파싱된 섹션 수: {len(sections)}")
    for section in sections:
        if section['type'] == 'article':
            print(f"  - 제{section['number']}조 ({section['title']}): {len(section['text'])} 글자")
    
    # 청킹 테스트
    print("\n2. 구조 기반 청킹")
    metadata = {
        'doc_name': '급여규정',
        'user_id': 'test_user'
    }
    chunks = chunker.chunk_by_structure(test_text, metadata)
    
    print(f"생성된 청크 수: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"\n[청크 {i+1}]")
        print(f"  크기: {len(chunk.page_content)} 글자")
        print(f"  hierarchy_path: {chunk.metadata.get('hierarchy_path', 'N/A')}")
        print(f"  미리보기: {chunk.page_content[:100]}...")
    
    print("\n테스트 완료!")


if __name__ == "__main__":
    test_structure_chunker()

