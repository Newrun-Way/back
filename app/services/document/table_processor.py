#app/services/document/table_processer.py
import json
from pathlib import Path
from app.core.config import get_settings

class TableProcessor:
    """
    file_path = metadata["file_path"] 를 기반으로
    /uploads/global/문서명.hwpx/tables/t001.json 을 읽어오는 로직.
    """

    def __init__(self, extracted_dir: str = None):
        settings = get_settings()
        # extracted_dir = UPLOAD_DIR
        self.base_dir = Path(extracted_dir or settings.EXTRACTED_DIR)

    def get_table(self, file_path: str, table_id: str):
        """
        file_path 예시:
        global/징계규칙(original)/original.hwpx
        """
        rel = Path(file_path)
        doc_dir = self.base_dir / rel.parent
        table_file = doc_dir / "tables" / f"{table_id}.json"

        if not table_file.exists():
            return None

        return json.loads(table_file.read_text())

    def load_tables_from_doc(self, file_path: str):
        """
        문서 전체 표 로딩
        """
        rel = Path(file_path)
        doc_dir = self.base_dir / rel.parent
        tables_dir = doc_dir / "tables"

        if not tables_dir.exists():
            return {}

        tables = {}
        for jf in tables_dir.glob("*.json"):
            data = json.loads(jf.read_text())
            tid = data.get("table_id", jf.stem)
            tables[tid] = data

        return tables
