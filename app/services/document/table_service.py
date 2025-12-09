# app/services/document/table_service.py

from pathlib import Path
from typing import List, Dict, Any

from app.core.config import get_settings
from app.services.document.table_processor import TableProcessor


class TableService:
    """
    문서별 표 데이터를 로딩/구조화해서 반환하는 서비스.
    - parser.py에서 저장한 {doc_name}_표데이터.json을 읽고
    - TableProcessor로 구조화된 table 객체 리스트를 반환한다.
    """

    def __init__(self):
        settings = get_settings()
        extracted_dir = Path(getattr(settings, "EXTRACTED_DIR", "extracted_results"))
        self.processor = TableProcessor(extracted_dir=extracted_dir)

    def get_tables_for_document(self, original_filename: str) -> List[Dict[str, Any]]:
        """
        original_filename 기준으로 해당 문서의 모든 표를 구조화해서 반환.

        Args:
            original_filename: DB에 저장된 원본 파일명
                               (예: '복무규정(2025년도 8월 22일 개정).hwpx')

        Returns:
            [
              { "table_id": "t001", "rows": [...], "cols": [...], ... },
              ...
            ]
        """
        # parser/save_tables_json에서 doc_name = Path(file_path).stem 을 사용했으므로
        # 여기서도 동일하게 stem만 사용해야 동일 디렉토리를 찾는다.
        doc_name = Path(original_filename).stem

        tables_dict = self.processor.load_tables_from_doc(doc_name)
        # TableProcessor.load_tables_from_doc()은 {table_id: table_data} 형태를 반환하므로
        # 프론트에 넘길 때는 리스트로 변환한다.
        return list(tables_dict.values())
