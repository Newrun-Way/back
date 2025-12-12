# app/services/document/table_service.py
from app.services.document.table_processor import TableProcessor
from app.core.config import get_settings

class TableService:
    def __init__(self):
        settings = get_settings()
        self.processor = TableProcessor(settings.EXTRACTED_DIR)

    def get_table(self, file_path: str, table_id: str):
        return self.processor.get_table(file_path, table_id)

    def get_all_tables(self, file_path: str):
        return self.processor.load_tables_from_doc(file_path)
