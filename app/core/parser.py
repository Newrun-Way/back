#app/core/parser.py
import zipfile
import json
from pathlib import Path
from lxml import etree
from app.core.config import get_settings

settings = get_settings()

def extract_hwpx_with_structure(hwpx_path: str):
    """
    HWPX 파일에서 문단 + 표 + 구조 정보를 추출.
    표 데이터는 original.hwpx와 같은 디렉토리에 tables/ 폴더를 생성하여 저장한다.
    """
    result = {
        "paragraphs": [],
        "tables": [],
        "structure": [],
        "structure_tree": {},
        "file_path": None,   # metadata용
    }

    hwpx_path = Path(hwpx_path)
    result["file_path"] = str(hwpx_path)  # 나중에 metadata에 저장됨

    # HWPX 압축 해제 및 XML 파싱
    with zipfile.ZipFile(hwpx_path, "r") as z:
        # Section*.xml 탐색
        section_files = [f for f in z.namelist() if f.startswith("Contents/Section")]
        for sec in section_files:
            xml_bytes = z.read(sec)
            root = etree.fromstring(xml_bytes)

            ns = {
                "hp": "http://www.hancom.co.kr/hwpml/2021/paragraph",
                "hs": "http://www.hancom.co.kr/hwpml/2018/section",
            }

            # 문단 추출
            paras = root.findall('.//hp:p', ns)
            for p_idx, p in enumerate(paras):
                text = ''.join(p.itertext()).strip()
                if text:
                    result["paragraphs"].append({
                        "text": text,
                        "paragraph_idx": len(result["paragraphs"]),
                    })

            # 표 추출
            tables = root.findall('.//hp:tbl', ns)
            for t_idx, table in enumerate(tables):
                table_id = f"t{t_idx:03d}"

                table_data = {
                    "table_id": table_id,
                    "rows": [],
                }

                rows = table.findall('.//hp:tr', ns)
                for row in rows:
                    cells = []
                    for cell in row.findall('.//hp:tc', ns):
                        cell_text = ''.join(cell.itertext()).strip()
                        cells.append(cell_text)
                    if cells:
                        table_data["rows"].append(cells)

                if table_data["rows"]:
                    result["tables"].append(table_data)

    # 표 JSON 저장 수행
    save_tables_json(hwpx_path, result["tables"])

    return result


def save_tables_json(hwpx_path: Path, tables: list):
    """
    표 JSON을 original.hwpx와 같은 디렉토리에 저장한다.
    /uploads/global/문서명.hwpx/tables/t001.json ...
    """
    # hwpx_path 예:
    # /app/app/data/uploads/global/징계규칙/ original.hwpx 에 해당하는 전체경로
    doc_dir = hwpx_path.parent
    tables_dir = doc_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    # 테이블별 JSON 저장
    for table in tables:
        table_id = table["table_id"]
        out_path = tables_dir / f"{table_id}.json"
        out_path.write_text(json.dumps(table, ensure_ascii=False, indent=2))

    return str(tables_dir)
