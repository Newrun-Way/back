# app/api/v1/endpoints/documents.py

from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from app.core.config import get_settings
from app.services.rag.rag_service import RAGService
from app.services.document.document_service import DocumentService
from app.services.document.table_service import TableService
from app.services.document.section_builder import SectionBuilder
import json

router = APIRouter(prefix="/documents", tags=["Documents"])
settings = get_settings()
doc_service = DocumentService()
section_builder = SectionBuilder()

GLOBAL_DIR_NAME = "global"
svc = DocumentService()
table_service = TableService()

@router.get("/")
def list_documents(dept_id: int | None = None, project_id: int | None = None):
    return svc.list(dept_id, project_id)


@router.get("/{doc_pk}")
def get_document_detail(doc_pk: int):
    """
    문서 상세 조회 (documents.id 기반)
    - DB 메타 + VectorDB chunks 통합
    - 구조 기반 청킹 메타데이터가 있으면 structure_tree 구성
    """
    # 1) DB에서 문서 조회
    doc = doc_service.get_by_id(doc_pk)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")

    external_doc_id = doc["external_doc_id"]
    original_filename = doc["original_filename"]
    print(f"[DEBUG] external_doc_id from DB: {external_doc_id}")
    print(f"[DEBUG] stored_path: {doc['stored_path']}")
    print(f"[DEBUG] status: {doc['status']}")

    # 2) RAG 서비스 접근
    try:
        rag = RAGService()
        col = rag.vector_store.collection
        print("[DEBUG] RAGService initialized. Vector collection OK.")
    except Exception as e:
        raise HTTPException(500, f"RAGService 초기화 실패: {e}")

    # 3) 벡터 DB에서 external_doc_id로 chunk 조회
    query_filter = {"external_doc_id": external_doc_id}
    print(f"[DEBUG] VectorDB Query filter = {query_filter}")

    try:
        result = col.get(
            where=query_filter,
            include=["documents", "metadatas"],
        )
    except Exception as e:
        print("[ERROR] VectorDB get() failed:", e)
        raise HTTPException(500, f"VectorDB get() failed: {e}")

    docs = result.get("documents", [])
    metas = result.get("metadatas", [])
    print(f"[DEBUG] VectorDB returned chunks = {len(docs)}")
    print(f"[DEBUG] VectorDB raw result keys = {result.keys()}")

    if len(docs) == 0:
        return {
            "id": doc_pk,
            "external_doc_id": external_doc_id,
            "original_filename": original_filename,
            "total_chunks": 0,
            "content": "",
            "summary": None,
            "structure_tree": None,
            "tables": [],
            "chunks": [],
            "message": f"VectorDB에 external_doc_id={external_doc_id} 로 저장된 chunk가 없습니다.",
        }

    # 4) 정렬 (chunk_id 우선, 없으면 paragraph_idx)
    items = list(zip(docs, metas))

    def _sort_key(item):
        meta = item[1] or {}
        if "chunk_id" in meta and meta["chunk_id"] is not None:
            return meta["chunk_id"]
        return meta.get("paragraph_idx", 0)

    items.sort(key=_sort_key)

    # 5) 전체 텍스트 merge
    merged_text = "\n".join([text for text, _ in items])

    # 6) 구조 기반 메타데이터가 있다면 structure_tree 구성
    structure_tree = None

    # chapter/article/hierarchy_path 메타가 하나라도 있으면 구조 있음으로 간주
    has_structure_meta = any(
        (m.get("chapter_num") is not None)
        or (m.get("article_num") is not None)
        or (m.get("hierarchy_path") is not None)
        for m in metas
        if isinstance(m, dict)
    )

    if has_structure_meta:
        # chapter_num → { chapter_node(with articles map) }
        chapters: dict[str, dict] = {}

        for text, meta in items:
            if not isinstance(meta, dict):
                continue

            chapter_num = meta.get("chapter_num")
            chapter_title = meta.get("chapter_title")
            article_num = meta.get("article_num")
            article_title = meta.get("article_title")
            hierarchy_path = meta.get("hierarchy_path")
            chunk_id = meta.get("chunk_id")

            # article 정보가 없으면 트리에 넣지 않음 (머리말 등)
            if article_num is None:
                continue

            ch_key = str(chapter_num) if chapter_num is not None else "0"

            # chapter 노드 준비
            if ch_key not in chapters:
                chapters[ch_key] = {
                    "number": chapter_num,
                    "title": chapter_title,
                    "summary": None,          # 장 요약 (추후 요약 엔진 연동)
                    "hierarchy_path": None,   # 필요시 채움
                    "articles": {},
                }

            ch_node = chapters[ch_key]

            # article 노드 준비
            articles_map = ch_node["articles"]
            art_key = str(article_num)

            if art_key not in articles_map:
                articles_map[art_key] = {
                    "number": article_num,
                    "title": article_title,
                    "summary": None,             # 조 요약 (추후 요약 엔진 연동)
                    "hierarchy_path": hierarchy_path,
                    "body": "",                  # 해당 조 전체 원문
                    "paragraphs": [],
                    "chunks": [],                # 조에 속한 청크들(옵션)
                }

            art_node = articles_map[art_key]

            # 조 본문(body) 누적
            if art_node["body"]:
                art_node["body"] += "\n" + text
            else:
                art_node["body"] = text

            # 단순 paragraph 리스트(옵션)로도 보관
            art_node["paragraphs"].append(
                {
                    "number": None,
                    "text": text,
                }
            )

            # 조 하위 chunk 목록 (원하면 프론트에서 사용할 수 있음)
            art_node["chunks"].append(
                {
                    "chunk_id": chunk_id,
                    "content": text,
                    "metadata": meta,
                }
            )

        # dict → 정렬된 리스트 구조로 변환
        chapter_list = []

        def _to_int_or_str(v):
            try:
                return int(v)
            except Exception:
                return v or 0

        for ch_key, ch_node in chapters.items():
            articles_map = ch_node["articles"]
            article_list = list(articles_map.values())
            article_list.sort(key=lambda a: _to_int_or_str(a["number"]))

            chapter_list.append(
                {
                    "number": ch_node["number"],
                    "title": ch_node["title"],
                    "summary": ch_node["summary"],
                    "hierarchy_path": ch_node.get("hierarchy_path"),
                    "articles": article_list,
                }
            )

        chapter_list.sort(key=lambda c: _to_int_or_str(c["number"]))
        structure_tree = {"chapters": chapter_list}

    # 7) 문서 단위 summary (있으면 사용, 없으면 None)
    #    - DB 컬럼 또는 향후 Celery 요약 엔진이 metadata에 넣어줄 수 있음
    doc_summary = doc.get("summary") if isinstance(doc, dict) else None

    # 8) 표 구조 로드
    tables = table_service.get_tables_for_document(original_filename)

    # 9) section JSON 생성
    sections = section_builder.build(structure_tree, tables)

    # 10) 응답
    return {
        "id": doc_pk,
        "external_doc_id": external_doc_id,
        "original_filename": original_filename,
        "total_chunks": len(items),
        "content": merged_text,
        "summary": doc_summary,
        "structure_tree": structure_tree,
        "sections": sections,
        "tables": tables,
        "chunks": [
            {
                "chunk_id": meta.get("chunk_id"),
                "paragraph_idx": meta.get("paragraph_idx"),
                "content": text,
                "metadata": meta,
            }
            for text, meta in items
        ],
    }


@router.get("/download/{doc_id}", summary="문서 다운로드 by PK id")
def download_document(doc_id: int):
    # 1) DB 조회 (PK 기준)
    doc = doc_service.get_by_id(doc_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")

    stored_path = doc["stored_path"]  # 예: global/감사규정_20240101_123000/original.hwp
    file_path = Path(settings.UPLOAD_DIR) / stored_path

    if not file_path.exists():
        raise HTTPException(404, f"파일을 찾을 수 없습니다: {file_path}")

    # 다운로드 파일명
    download_name = doc["original_filename"]

    return FileResponse(
        path=str(file_path),
        filename=download_name,
        media_type="application/octet-stream"
    )

@router.get("/{doc_id}/text")
def get_document_full_text(doc_id: int):
    """
    original_전체텍스트.txt 제공 (프론트용)
    """
    # 1) DB에서 문서 조회 (예시)
    doc = doc_service.get_by_id(doc_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")

    file_path = Path(doc["file_path"])  # global/징계규칙(...).hwpx
    doc_dir = Path(settings.EXTRACTED_DIR) / file_path.parent
    text_file = doc_dir / f"{file_path.stem}_전체텍스트.txt"

    if not text_file.exists():
        raise HTTPException(404, "전체 텍스트 파일이 없습니다.")

    return FileResponse(
        path=text_file,
        media_type="text/plain",
        # filename=text_file.name,
        headers={"Content-Disposition": "inline"},#미리보기로 제공
    )