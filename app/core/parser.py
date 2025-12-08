import zipfile
import xml.etree.ElementTree as ET
import json
import os
from pathlib import Path
from .jpype_setup import init_jpype
import logging
import time
import re
logger = logging.getLogger(__name__)

def analyze_document_structure(text_lines):
    """
    문서 텍스트 줄 리스트에서 장/조/항/호 구조 정보를 분석한다.
    OWPML1 extract.py 구조와 동일한 원형 설계 기반.
    """

    structure = {
        "chapters": [],
        "articles": [],
        "structure_map": {}
    }

    current_chapter = None
    current_article = None

    patterns = {
        "chapter": re.compile(r'^제\s*(\d+)\s*장\s+(.+)$'),
        "article": re.compile(r'^제\s*(\d+)\s*조\s*(?:\((.+?)\))?(.*)$'),
        "paragraph": re.compile(r'^([①②③④⑤⑥⑦⑧⑨⑩]|\d+\))\s*(.*)$'),
        "subparagraph": re.compile(r'^([가나다라마바사아자차카타파하])\.\s+(.*)$')
    }

    for line_idx, line in enumerate(text_lines):
        line = line.strip()
        if not line:
            continue

        # 장
        chapter_match = patterns["chapter"].match(line)
        if chapter_match:
            num = chapter_match.group(1)
            title = chapter_match.group(2).strip()

            current_chapter = {
                "number": num,
                "title": title,
                "line_idx": line_idx,
                "articles": []
            }
            structure["chapters"].append(current_chapter)
            structure["structure_map"][line_idx] = {
                "type": "chapter",
                "number": num,
                "title": title
            }
            continue

        # 조
        article_match = patterns["article"].match(line)
        if article_match:
            num = article_match.group(1)
            title = article_match.group(2).strip() if article_match.group(2) else ""

            current_article = {
                "number": num,
                "title": title,
                "line_idx": line_idx,
                "chapter_num": current_chapter["number"] if current_chapter else None,
                "paragraphs": []
            }

            if current_chapter:
                current_chapter["articles"].append(current_article)

            structure["articles"].append(current_article)
            structure["structure_map"][line_idx] = {
                "type": "article",
                "number": num,
                "title": title,
                "chapter_num": current_chapter["number"] if current_chapter else None
            }
            continue

        # 항
        para_match = patterns["paragraph"].match(line)
        if para_match:
            num = para_match.group(1)

            korean_map = {"①": "1", "②": "2", "③": "3", "④": "4", "⑤": "5",
                          "⑥": "6", "⑦": "7", "⑧": "8", "⑨": "9", "⑩": "10"}
            normalized = korean_map.get(num, num.rstrip(")"))

            if current_article:
                current_article["paragraphs"].append({
                    "number": normalized,
                    "line_idx": line_idx
                })

            structure["structure_map"][line_idx] = {
                "type": "paragraph",
                "number": normalized,
                "article_num": current_article["number"] if current_article else None,
                "chapter_num": current_chapter["number"] if current_chapter else None
            }
            continue

        # 호
        subpara_match = patterns["subparagraph"].match(line)
        if subpara_match:
            letter = subpara_match.group(1)

            structure["structure_map"][line_idx] = {
                "type": "subparagraph",
                "letter": letter,
                "article_num": current_article["number"] if current_article else None,
                "chapter_num": current_chapter["number"] if current_chapter else None
            }

    return structure

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

    # 구조 분석 추가
    full_text = "\n".join(result["text_content"])
    text_lines = full_text.split("\n")

    doc_structure = analyze_document_structure(text_lines)
    result["structure"] = doc_structure
    result["structure_tree"] = build_structure_tree(doc_structure)

    end_time = time.time()
    logger.info(f"Finished document parsing for {file_path} in {end_time - start_time:.2f} seconds")
    return result

def build_structure_tree(doc_structure: dict) -> dict:
    """
    parser.analyze_document_structure()가 만든 구조 정보를 기반으로
    chapter → article → paragraph 트리 구조를 생성한다.

    Input: doc_structure = {
        "chapters": [...],
        "articles": [...],
        "structure_map": {...}
    }

    Output: {
      "chapters": [
        {
          "number": "1",
          "title": "총칙",
          "articles": [
            {
              "number": "1",
              "title": "",
              "paragraphs": [
                {"number": "1", "line_idx": 130},
                ...
              ]
            }
          ]
        }
      ]
    }
    """
    if not doc_structure:
        return {"chapters": []}

    chapters = doc_structure.get("chapters", [])
    articles = doc_structure.get("articles", [])

    # 1️⃣ chapter_num → chapter object 매핑
    chapter_map = {ch.get("number"): ch for ch in chapters}

    # 2️⃣ tree 기본 구조 생성
    tree = {"chapters": []}

    # chapter 기반 구조 생성
    for ch in chapters:
        tree["chapters"].append({
            "number": ch.get("number"),
            "title": ch.get("title"),
            "articles": [],  # 나중에 채움
        })

    # chapter number → tree chapter object 매핑
    chapter_tree_map = {c["number"]: c for c in tree["chapters"]}

    # 3️⃣ article → paragraph 매핑 후 chapter에 삽입
    for art in articles:
        chapter_num = art.get("chapter_num")
        if not chapter_num:
            continue  # chapter 없는 조는 드물지만 방어 처리

        chapter_node = chapter_tree_map.get(chapter_num)
        if not chapter_node:
            continue

        article_node = {
            "number": art.get("number"),
            "title": art.get("title"),
            "paragraphs": art.get("paragraphs", []),
        }
        chapter_node["articles"].append(article_node)

    return tree
