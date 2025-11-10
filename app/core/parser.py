import zipfile
import xml.etree.ElementTree as ET
import json
import os
from pathlib import Path
from .jpype_setup import init_jpype
import logging
import time

logger = logging.getLogger(__name__)

def extract_hwpx_with_structure(hwpx_path):
    """HWPX 파일에서 구조화된 데이터 추출"""
    logger.info(f"Starting HWPX extraction for {hwpx_path}")
    start_time = time.time()

    result = {
        "text_content": [],
        "tables": [],
        "images": [],
        "metadata": {},
        "paragraphs": [],
        "file_type": "HWPX"
    }

    # HWPX는 ZIP 파일
    with zipfile.ZipFile(hwpx_path, 'r') as z:
        
        # 메타데이터 추출
        try:
            header_xml = z.read('Contents/header.xml').decode('utf-8')
            header_root = ET.fromstring(header_xml)
            result["metadata"]["header"] = "추출됨"
        except:
            pass
        
        # Section 파일들 처리
        section_files = [f for f in z.namelist() if f.startswith('Contents/section') and f.endswith('.xml')]
        
        for section_file in section_files:
            section_xml = z.read(section_file).decode('utf-8')
            root = ET.fromstring(section_xml)
            
            # 네임스페이스 정의
            ns = {
                'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
                'hc': 'http://www.hancom.co.kr/hwpml/2011/core'
            }
            
            # 텍스트 추출 (단락별)
            paragraphs = root.findall('.//hp:p', ns)
            for i, para in enumerate(paragraphs):
                para_text = ''.join(para.itertext()).strip()
                if para_text:
                    result["paragraphs"].append({
                        "id": i,
                        "text": para_text,
                        "type": "paragraph"
                    })
                    result["text_content"].append(para_text)
            
            # 표(Table) 추출
            tables = root.findall('.//hp:tbl', ns)
            for t_idx, table in enumerate(tables):
                table_data = {
                    "id": t_idx,
                    "type": "table",
                    "rows": [],
                    "summary": ""
                }
                
                # 표의 각 행(tr) 처리
                rows = table.findall('.//hp:tr', ns)
                for row in rows:
                    cells = []
                    # 각 셀(tc) 처리
                    for cell in row.findall('.//hp:tc', ns):
                        cell_text = ''.join(cell.itertext()).strip()
                        cells.append(cell_text)
                    if cells:
                        table_data["rows"].append(cells)
                
                if table_data["rows"]:
                    # 표 요약 생성
                    table_data["summary"] = f"표 {t_idx + 1}: {len(table_data['rows'])}행 × {len(table_data['rows'][0])}열"
                    result["tables"].append(table_data)
                    
                    # 텍스트 컨텐츠에도 표시
                    result["text_content"].append(f"\n[{table_data['summary']}]\n")
        
        # 이미지 추출 (이미지 데이터는 직접 반환하지 않고, 메타데이터만 포함)
        image_files = [f for f in z.namelist() if f.startswith('BinData/') and 
                      any(f.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif'])]
        
        for img_file in image_files:
            img_name = os.path.basename(img_file)
            result["images"].append({
                "filename": img_name,
                "size": z.getinfo(img_file).file_size
            })
    
    end_time = time.time()
    logger.info(f"Finished HWPX extraction for {hwpx_path} in {end_time - start_time:.2f} seconds")
    return result


def extract_hwp_text(hwp_jar_path, hwp_path):
    """HWP 파일에서 텍스트 추출"""
    logger.info(f"Starting HWP extraction for {hwp_path} using JAR: {hwp_jar_path}")
    start_time = time.time()

    result = {
        "text_content": [],
        "tables": [],
        "images": [],
        "metadata": {},
        "paragraphs": [],
        "file_type": "HWP"
    }

    # jpype 초기화 (JAVA_HOME 자동 설정 + JVM 시작)
    try:
        print('인잇 시작')
        jpype = init_jpype(hwp_jar_path)
        logger.info("JPype initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize JPype: {e}", exc_info=True)
        raise

    try:
        # Java 패키지 가져오기
        HWPReader_class = jpype.JPackage('kr.dogfoot.hwplib.reader')
        TextExtrac_class = jpype.JPackage('kr.dogfoot.hwplib.tool.textextractor')
        HWPReader_ = HWPReader_class.HWPReader
        TextExtractMethod_ = TextExtrac_class.TextExtractMethod
        TextExtractor_ = TextExtrac_class.TextExtractor
        
        # HWP 파일 읽기
        hwp_file = HWPReader_.fromFile(hwp_path)
        
        # 전체 텍스트 추출
        full_text = TextExtractor_.extract(hwp_file, TextExtractMethod_.InsertControlTextBetweenParagraphText)
        result["text_content"] = [full_text]
        
        # 메타데이터
        result["metadata"]["note"] = "HWP 파일은 텍스트만 추출됩니다. 표/이미지가 필요하면 HWPX로 저장하세요."
        
    except Exception as e:
        logger.error(f"Error during HWP text extraction: {e}", exc_info=True)
        raise
    finally:
        pass

    end_time = time.time()
    logger.info(f"Finished HWP extraction for {hwp_path} in {end_time - start_time:.2f} seconds")
    return result


def parse_document(file_path: str, *, doc_id: str | None = None, meta: dict | None = None):
    """HWP/HWPX 파일을 파싱하고 구조화된 JSON 데이터를 반환합니다."""
    logger.info(f"Starting document parsing for {file_path}")
    start_time = time.time()

    file_ext = Path(file_path).suffix.lower()

    if file_ext not in ['.hwp', '.hwpx']:
        raise ValueError(f"지원하지 않는 파일 형식입니다: {file_ext}. .hwp 또는 .hwpx 파일만 지원합니다.")

    if file_ext == '.hwpx':
        # HWPX: 표, 이미지 포함 완벽 추출
        result = extract_hwpx_with_structure(file_path)
    else:  # .hwp
        # HWP: 텍스트만 추출
        # JAR 파일 경로 (back/app/python-hwplib/hwplib-1.1.8.jar)
        current_dir = Path(__file__).parent
        hwp_jar_path = str(current_dir.parent / "python-hwplib" / "hwplib-1.1.8.jar")

        if not os.path.exists(hwp_jar_path):
            raise FileNotFoundError(f"hwplib JAR 파일을 찾을 수 없습니다: {hwp_jar_path}")

        # HWP 추출
        result = extract_hwp_text(hwp_jar_path, file_path)
    
    result["doc_id"] = doc_id or Path(file_path).stem
    merged_meta = result.get("metadata", {})
    if meta:
        merged_meta.update(meta)
    result["metadata"] = merged_meta
    
    end_time = time.time()
    logger.info(f"Finished document parsing for {file_path} in {end_time - start_time:.2f} seconds")
    return result
