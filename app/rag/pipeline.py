"""
RAG 파이프라인
전체 시스템 통합 및 질의응답 처리
"""

from typing import List, Dict
from pathlib import Path
import json
from langchain_core.documents import Document
from loguru import logger

from .chunker import DocumentChunker
from .embedder import DocumentEmbedder
from .vector_store import VectorStore
from .llm import LLMGenerator


class RAGPipeline:
    """RAG 파이프라인 클래스"""
    
    def __init__(
        self, 
        settings: object
    ):
        """
        Args:
            settings: FastAPI settings object
        """
        logger.info("RAG 파이프라인 초기화 중...")
        self.settings = settings

        # 각 모듈 초기화
        self.chunker = DocumentChunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=settings.SEPARATORS
        )
        self.embedder = DocumentEmbedder(
            model_name=settings.EMBEDDING_MODEL
        )
        self.llm = LLMGenerator(
            api_key=settings.OPENAI_API_KEY,
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            system_prompt=settings.SYSTEM_PROMPT,
            user_prompt_template=settings.USER_PROMPT_TEMPLATE
        )
        
        # 벡터 저장소 로드 또는 생성
        self.vector_store_dir = Path(settings.VECTOR_STORE_DIR)
        if (self.vector_store_dir / "metadata.pkl").exists():
            logger.info("기존 벡터 저장소 로드 중...")
            self.vector_store = VectorStore.load(self.vector_store_dir)
        else:
            logger.info("새 벡터 저장소 생성")
            self.vector_store = VectorStore(
                embedding_dim=self.embedder.get_embedding_dim()
            )
        
        logger.info("RAG 파이프라인 초기화 완료")
    
    def add_document_from_extract(
        self,
        extracted_dir: Path
    ):
        """
        extract.py로 추출된 문서를 RAG 시스템에 추가
        
        Args:
            extracted_dir: 추출된 결과 디렉토리 (extracted_results/extracted_문서명/)
        """
        extracted_dir = Path(extracted_dir)
        
        # 파일 찾기
        text_file = None
        structure_file = None
        for file in extracted_dir.glob("*"):
            if "전체텍스트" in file.name:
                text_file = file
            elif "구조" in file.name:
                structure_file = file
        
        if not text_file:
            raise FileNotFoundError(f"텍스트 파일을 찾을 수 없습니다: {extracted_dir}")
        
        # 텍스트 로드
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # 구조 정보 로드 (있으면)
        tables = []
        metadata = {'doc_name': extracted_dir.stem.replace('extracted_', '')}
        
        if structure_file:
            with open(structure_file, 'r', encoding='utf-8') as f:
                structure = json.load(f)
                metadata['file_type'] = structure.get('file_type', 'unknown')
        
        # 표 데이터 로드 (있으면)
        for file in extracted_dir.glob("*표데이터*"):
            with open(file, 'r', encoding='utf-8') as f:
                tables = json.load(f)
            break
        
        logger.info(f"문서 추가 중: {metadata['doc_name']}")
        logger.info(f"  텍스트 길이: {len(text)} 글자")
        logger.info(f"  표 개수: {len(tables)}개")
        
        # 청킹
        if tables:
            chunks = self.chunker.chunk_with_tables(text, tables, metadata)
        else:
            chunks = self.chunker.chunk_text(text, metadata)
        
        # 임베딩
        embeddings = self.embedder.embed_documents(chunks)
        
        # 벡터 저장소에 추가
        self.vector_store.add_documents(chunks, embeddings)
        
        # 저장
        self.vector_store.save(self.vector_store_dir)
        
        logger.info(f"문서 추가 완료: {len(chunks)}개 청크")
    
    def add_documents_batch(
        self,
        extracted_results_dir: Path
    ):
        """
        extracted_results 디렉토리의 모든 문서를 일괄 추가
        
        Args:
            extracted_results_dir: extracted_results 디렉토리 경로
        """
        extracted_results_dir = Path(extracted_results_dir)
        
        if not extracted_results_dir.exists():
            logger.warning(f"디렉토리가 존재하지 않습니다: {extracted_results_dir}")
            return
        
        # extracted_* 디렉토리 찾기
        extracted_dirs = [d for d in extracted_results_dir.iterdir() 
                         if d.is_dir() and d.name.startswith('extracted_')]
        
        logger.info(f"일괄 처리 시작: {len(extracted_dirs)}개 문서")
        
        for extracted_dir in extracted_dirs:
            try:
                self.add_document_from_extract(extracted_dir)
            except Exception as e:
                logger.error(f"문서 추가 실패 {extracted_dir.name}: {e}")
        
        logger.info("일괄 처리 완료")
    
    def query(
        self,
        question: str,
        return_sources: bool = True
    ) -> Dict:
        """
        질문에 대한 답변 생성
        
        Args:
            question: 사용자 질문
            return_sources: 출처 반환 여부
        
        Returns:
            {
                "answer": str,
                "sources": List[Dict] (if return_sources=True),
                "question": str,
                "processing_time": float
            }
        """
        import time
        start_time = time.time()
        
        logger.info(f"질문 처리 중: {question}")
        
        # 1. 질문 임베딩
        query_embedding = self.embedder.embed_query(question)
        
        # 2. 유사 문서 검색
        search_results = self.vector_store.search(
            query_embedding, 
            top_k=self.settings.TOP_K,
            threshold=self.settings.SIMILARITY_THRESHOLD
        )
        
        if not search_results:
            logger.warning("검색 결과 없음")
            return {
                "answer": "관련 문서를 찾을 수 없습니다. 다른 질문을 시도해보세요.",
                "sources": [],
                "question": question,
                "processing_time": time.time() - start_time
            }
        
        # 3. 컨텍스트 구성
        contexts = []
        for doc, score in search_results:
            contexts.append({
                'content': doc.page_content,
                'metadata': doc.metadata,
                'score': score
            })
        
        # 4. 답변 생성
        result = self.llm.generate_with_sources(contexts, question)
        
        # 5. 결과 반환
        response = {
            "answer": result['answer'],
            "question": question,
            "processing_time": time.time() - start_time
        }
        
        if return_sources:
            response["sources"] = result['sources']
        
        logger.info(f"질문 처리 완료 ({response['processing_time']:.2f}초)")
        return response
    
    def get_stats(self) -> Dict:
        """시스템 통계 반환"""
        return {
            'vector_store': self.vector_store.get_stats(),
            'embedding_model': self.embedder.model_name,
            'llm_model': self.llm.model
        }


def test_pipeline():
    """파이프라인 전체 테스트"""
    import os
    
    # API 키 확인
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY 환경변수를 설정해주세요")
        return
    
    print("\n=== RAG 파이프라인 테스트 ===\n")
    
    # 파이프라인 초기화
    pipeline = RAGPipeline(load_existing=False)
    
    # 테스트 문서 추가 (extracted_results에서)
    extracted_results_dir = Path("extracted_results")
    if extracted_results_dir.exists():
        print(f"extracted_results 디렉토리에서 문서 로드 중...")
        pipeline.add_documents_batch(extracted_results_dir)
    else:
        print(f"extracted_results 디렉토리가 없습니다.")
        print(f"먼저 extract.py로 문서를 추출하세요.")
        return
    
    # 통계 출력
    stats = pipeline.get_stats()
    print(f"\n시스템 통계:")
    print(f"  - 총 문서 수: {stats['vector_store']['total_documents']}")
    print(f"  - 임베딩 모델: {stats['embedding_model']}")
    print(f"  - LLM 모델: {stats['llm_model']}")
    
    # 질의응답 테스트
    test_questions = [
        "이 문서의 주요 내용은 무엇인가요?",
        "포상 대상자는 누구인가요?",
        "신청 기한은 언제까지인가요?"
    ]
    
    for question in test_questions:
        print(f"\n{'='*60}")
        print(f"질문: {question}")
        print(f"{'='*60}")
        
        result = pipeline.query(question)
        
        print(f"\n답변:\n{result['answer']}")
        print(f"\n처리 시간: {result['processing_time']:.2f}초")
        
        if result.get('sources'):
            print(f"\n출처:")
            for source in result['sources']:
                print(f"  - {source['doc_name']} (청크 {source['chunk_id']}, score: {source['score']:.4f})")


if __name__ == "__main__":
    test_pipeline()

