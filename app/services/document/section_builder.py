# app/services/document/section_builder.py

from __future__ import annotations
from typing import Any, Dict, List, Optional


class SectionBuilder:
    """
    structure_tree + tables 를 기반으로
    프론트에서 바로 쓸 수 있는 section JSON을 만들어준다.

    입력 예시 (structure_tree):

    {
      "chapters": [
        {
          "number": "1",
          "title": "총칙",
          "summary": null,
          "hierarchy_path": null,
          "articles": [
            {
              "number": "1",
              "title": "목적",
              "summary": null,
              "hierarchy_path": "제1장 총칙 > 제1조 목적",
              "body": "① ...\n② ...",
              "paragraphs": [
                {"number": "1", "text": "① ..."},
                {"number": "2", "text": "② ..."}
              ]
            }
          ]
        }
      ]
    }

    출력 예시 (sections):

    [
      {
        "id": "1",
        "type": "chapter",
        "number": "1",
        "title": "총칙",
        "summary": null,
        "hierarchy_path": "제1장 총칙",
        "children": [
          {
            "id": "1-1",
            "type": "article",
            "number": "1",
            "title": "목적",
            "summary": null,
            "hierarchy_path": "제1장 총칙 > 제1조 목적",
            "body": "① ...\n② ...",
            "children": [
              {
                "id": "1-1-1",
                "type": "paragraph",
                "number": "1",
                "text": "① ...",
                "hierarchy_path": "제1장 총칙 > 제1조 목적 > 제1항"
              },
              ...
            ]
          }
        ]
      },
      {
        "id": "table-1",
        "type": "table",
        "title": "...",
        "table": { ... }   # table_processor 구조화 결과
      }
    ]
    """

    def build(
        self,
        structure_tree: Optional[Dict[str, Any]],
        tables: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        if not structure_tree:
            return self._build_only_tables(tables or [])

        chapters = structure_tree.get("chapters") or []
        sections: List[Dict[str, Any]] = []

        for ch_idx, ch in enumerate(chapters, start=1):
            chapter_section = self._build_chapter_section(ch, ch_idx)
            sections.append(chapter_section)

        # 도큐먼트 레벨 테이블을 별도 section으로 추가
        for t_idx, table in enumerate(tables or [], start=1):
            sections.append(self._build_table_section(table, t_idx))

        return sections

    # ------------------------------------------------------------------
    # 내부 빌더들
    # ------------------------------------------------------------------
    def _build_chapter_section(self, ch: Dict[str, Any], ch_idx: int) -> Dict[str, Any]:
        ch_num = ch.get("number") or ch_idx
        ch_title = ch.get("title") or ""
        ch_summary = ch.get("summary")
        ch_hp = ch.get("hierarchy_path") or self._build_chapter_path(ch_num, ch_title)

        chapter_id = str(ch_num)

        chapter_section: Dict[str, Any] = {
            "id": chapter_id,
            "type": "chapter",
            "number": ch_num,
            "title": ch_title,
            "summary": ch_summary,
            "hierarchy_path": ch_hp,
            "children": [],
        }

        articles = ch.get("articles") or []
        for a_idx, art in enumerate(articles, start=1):
            article_section = self._build_article_section(
                art, chapter_id, ch_num, ch_title, a_idx
            )
            chapter_section["children"].append(article_section)

        return chapter_section

    def _build_article_section(
        self,
        art: Dict[str, Any],
        chapter_id: str,
        ch_num: Any,
        ch_title: str,
        a_idx: int,
    ) -> Dict[str, Any]:
        art_num = art.get("number") or a_idx
        art_title = art.get("title") or ""
        art_summary = art.get("summary")
        art_body = art.get("body") or ""
        art_hp = art.get("hierarchy_path") or self._build_article_path(
            ch_num, ch_title, art_num, art_title
        )

        article_id = f"{chapter_id}-{art_num}"

        article_section: Dict[str, Any] = {
            "id": article_id,
            "type": "article",
            "number": art_num,
            "title": art_title,
            "summary": art_summary,
            "hierarchy_path": art_hp,
            "body": art_body,
            "children": [],
        }

        # paragraph 정보가 있으면 사용, 없으면 body를 줄 단위로 나눔
        paragraphs = self._extract_paragraphs(art)
        for p_idx, para in enumerate(paragraphs, start=1):
            para_num = para.get("number") or p_idx
            para_text = para.get("text") or para.get("content") or ""
            if not para_text.strip():
                continue

            para_id = f"{article_id}-{para_num}"
            para_hp = f"{art_hp} > 제{para_num}항"

            article_section["children"].append(
                {
                    "id": para_id,
                    "type": "paragraph",
                    "number": para_num,
                    "text": para_text,
                    "hierarchy_path": para_hp,
                }
            )

        return article_section

    def _build_table_section(self, table: Dict[str, Any], idx: int) -> Dict[str, Any]:
        title = (
            table.get("title")
            or table.get("name")
            or table.get("summary")
            or f"표 {idx}"
        )
        return {
            "id": f"table-{idx}",
            "type": "table",
            "title": title,
            "table": table,
        }

    def _build_only_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        sections: List[Dict[str, Any]] = []
        for idx, table in enumerate(tables, start=1):
            sections.append(self._build_table_section(table, idx))
        return sections

    # ------------------------------------------------------------------
    # 유틸
    # ------------------------------------------------------------------
    def _build_chapter_path(self, ch_num: Any, ch_title: str) -> str:
        if ch_title:
            return f"제{ch_num}장 {ch_title}"
        return f"제{ch_num}장"

    def _build_article_path(
        self,
        ch_num: Any,
        ch_title: str,
        art_num: Any,
        art_title: str,
    ) -> str:
        base = self._build_chapter_path(ch_num, ch_title)
        if art_title:
            return f"{base} > 제{art_num}조 {art_title}"
        return f"{base} > 제{art_num}조"

    def _extract_paragraphs(self, art: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        art["paragraphs"]가 있으면 사용하고, 없으면 body를 줄 단위로 나눠 paragraph 리스트를 생성.
        """
        paragraphs = art.get("paragraphs")
        if paragraphs and isinstance(paragraphs, list):
            # 이미 문단 정보가 있는 경우
            out: List[Dict[str, Any]] = []
            for p in paragraphs:
                if not isinstance(p, dict):
                    continue
                text = p.get("text") or p.get("content")
                if text and text.strip():
                    out.append(
                        {
                            "number": p.get("number"),
                            "text": text,
                        }
                    )
            if out:
                return out

        # paragraphs가 없거나 비어있으면 body로부터 생성
        body = art.get("body") or ""
        if not body.strip():
            return []

        # 두 줄 이상의 공백 기준으로 1차 분리
        chunks = [b.strip() for b in body.split("\n\n") if b.strip()]
        paragraphs: List[Dict[str, Any]] = []
        for idx, ch in enumerate(chunks, start=1):
            paragraphs.append({"number": idx, "text": ch})
        return paragraphs
