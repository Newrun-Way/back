"""
표 참조 처리 모듈
표 데이터를 로드하고 HTML/Markdown으로 변환하는 후처리 로직
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger


class TableProcessor:
    """표 참조 처리 클래스"""
    
    def __init__(self, extracted_dir: Path = None):
        """
        Args:
            extracted_dir: 추출된 결과 디렉토리 (extracted_results/)
        """
        self.extracted_dir = extracted_dir or Path("extracted_results")
        self.table_cache = {}  # {doc_name: {table_id: table_data}}
        
        logger.info(f"TableProcessor 초기화: {self.extracted_dir}")
    
    def load_tables_from_doc(self, doc_name: str) -> Dict[str, Dict]:
        """
        문서의 표 데이터를 로드
        
        Args:
            doc_name: 문서명 (예: "인사규정")
        
        Returns:
            {table_id: table_data} 딕셔너리
        """
        # 캐시 확인
        if doc_name in self.table_cache:
            return self.table_cache[doc_name]
        
        # 표데이터.json 파일 찾기
        doc_dir = self.extracted_dir / f"extracted_{doc_name}"
        if not doc_dir.exists():
            logger.warning(f"문서 디렉토리를 찾을 수 없습니다: {doc_dir}")
            return {}
        
        table_file = None
        for file in doc_dir.glob("*표데이터.json"):
            table_file = file
            break
        
        if not table_file or not table_file.exists():
            logger.info(f"표 데이터 파일이 없습니다: {doc_name}")
            return {}
        
        # JSON 로드
        try:
            with open(table_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # table_id로 인덱싱
            tables = {}
            
            # data가 리스트인 경우 (extract.py의 출력 형식)
            if isinstance(data, list):
                table_list = data
            # data가 딕셔너리이고 'tables' 키가 있는 경우
            elif isinstance(data, dict) and 'tables' in data:
                table_list = data['tables']
            else:
                table_list = []
            
            for i, table in enumerate(table_list):
                # table_id가 있으면 사용, 없으면 생성
                table_id = table.get('table_id', f"t{i+1:03d}")
                tables[table_id] = table
            
            # 캐시 저장
            self.table_cache[doc_name] = tables
            
            logger.info(f"표 데이터 로드 완료: {doc_name} ({len(tables)}개)")
            return tables
            
        except Exception as e:
            logger.error(f"표 데이터 로드 실패: {doc_name}, {e}")
            return {}
    
    def get_table(self, doc_name: str, table_id: str) -> Optional[Dict]:
        """
        특정 표 데이터 가져오기
        
        Args:
            doc_name: 문서명
            table_id: 표 ID (예: "t001")
        
        Returns:
            표 데이터 또는 None
        """
        tables = self.load_tables_from_doc(doc_name)
        return tables.get(table_id)
    
    def table_to_html(self, table_data: Dict) -> str:
        """
        표 데이터를 HTML로 변환
        
        Args:
            table_data: 표 데이터
        
        Returns:
            HTML 문자열
        """
        if not table_data:
            return ""
        
        rows = table_data.get('rows', [])
        if not rows:
            return ""
        
        html_parts = ['<table border="1" style="border-collapse: collapse; width: 100%;">']
        
        # 첫 행은 헤더로 처리
        if len(rows) > 0:
            html_parts.append('  <thead>')
            html_parts.append('    <tr>')
            
            # rows[0]이 리스트인 경우 (extract.py 형식)
            if isinstance(rows[0], list):
                for cell in rows[0]:
                    html_parts.append(f'      <th style="padding: 8px; background-color: #f2f2f2;">{cell}</th>')
            # rows[0]이 딕셔너리인 경우
            else:
                for cell in rows[0].get('cells', []):
                    text = cell.get('text', '')
                    colspan = cell.get('colspan', 1)
                    rowspan = cell.get('rowspan', 1)
                    col_attr = f' colspan="{colspan}"' if colspan > 1 else ''
                    row_attr = f' rowspan="{rowspan}"' if rowspan > 1 else ''
                    html_parts.append(f'      <th{col_attr}{row_attr} style="padding: 8px; background-color: #f2f2f2;">{text}</th>')
            
            html_parts.append('    </tr>')
            html_parts.append('  </thead>')
        
        # 나머지 행은 데이터
        if len(rows) > 1:
            html_parts.append('  <tbody>')
            for row in rows[1:]:
                html_parts.append('    <tr>')
                
                # row가 리스트인 경우 (extract.py 형식)
                if isinstance(row, list):
                    for cell in row:
                        html_parts.append(f'      <td style="padding: 8px; text-align: center;">{cell}</td>')
                # row가 딕셔너리인 경우
                else:
                    for cell in row.get('cells', []):
                        text = cell.get('text', '')
                        colspan = cell.get('colspan', 1)
                        rowspan = cell.get('rowspan', 1)
                        col_attr = f' colspan="{colspan}"' if colspan > 1 else ''
                        row_attr = f' rowspan="{rowspan}"' if rowspan > 1 else ''
                        html_parts.append(f'      <td{col_attr}{row_attr} style="padding: 8px; text-align: center;">{text}</td>')
                
                html_parts.append('    </tr>')
            html_parts.append('  </tbody>')
        
        html_parts.append('</table>')
        
        return '\n'.join(html_parts)
    
    def table_to_markdown(self, table_data: Dict) -> str:
        """
        표 데이터를 Markdown으로 변환
        
        Args:
            table_data: 표 데이터
        
        Returns:
            Markdown 문자열
        """
        if not table_data:
            return ""
        
        rows = table_data.get('rows', [])
        if not rows:
            return ""
        
        md_parts = []
        
        # 첫 행 (헤더)
        if len(rows) > 0:
            # rows[0]이 리스트인 경우 (extract.py 형식)
            if isinstance(rows[0], list):
                header_cells = rows[0]
            # rows[0]이 딕셔너리인 경우
            else:
                header_cells = [cell.get('text', '') for cell in rows[0].get('cells', [])]
            
            md_parts.append('| ' + ' | '.join(header_cells) + ' |')
            md_parts.append('| ' + ' | '.join(['---'] * len(header_cells)) + ' |')
        
        # 데이터 행
        for row in rows[1:]:
            # row가 리스트인 경우 (extract.py 형식)
            if isinstance(row, list):
                data_cells = row
            # row가 딕셔너리인 경우
            else:
                data_cells = [cell.get('text', '') for cell in row.get('cells', [])]
            
            md_parts.append('| ' + ' | '.join(data_cells) + ' |')
        
        return '\n'.join(md_parts)
    
    def process_sources_with_tables(
        self,
        sources: List[Dict],
        format: str = 'html'
    ) -> List[Dict]:
        """
        검색 결과 sources에서 table_id를 찾아 표 데이터를 추가
        
        Args:
            sources: 검색된 소스 리스트
                [
                    {
                        "doc_name": "인사규정",
                        "hierarchy_path": "제3장 > 제15조",
                        "content": "...",
                        "metadata": {
                            "table_id": "t001",
                            ...
                        }
                    },
                    ...
                ]
            format: 변환 형식 ('html' 또는 'markdown')
        
        Returns:
            표 정보가 추가된 sources
                [
                    {
                        "doc_name": "인사규정",
                        "hierarchy_path": "제3장 > 제15조",
                        "content": "...",
                        "table": {
                            "table_id": "t001",
                            "html": "<table>...</table>",
                            "markdown": "| ... |",
                            "location": "제3장 > 제15조"
                        }
                    },
                    ...
                ]
        """
        enhanced_sources = []
        
        for source in sources:
            enhanced_source = source.copy()
            
            # metadata에서 table_id 찾기
            metadata = source.get('metadata', {})
            table_id = metadata.get('table_id')
            
            if table_id and table_id != 'null' and table_id != '':
                doc_name = source.get('doc_name', '')
                
                # 표 데이터 로드
                table_data = self.get_table(doc_name, table_id)
                
                if table_data:
                    # 표 정보 추가
                    table_info = {
                        'table_id': table_id,
                        'location': source.get('hierarchy_path', ''),
                        'html': self.table_to_html(table_data) if format in ['html', 'both'] else '',
                        'markdown': self.table_to_markdown(table_data) if format in ['markdown', 'both'] else ''
                    }
                    enhanced_source['table'] = table_info
                    
                    logger.info(f"표 참조 처리 완료: {doc_name} / {table_id}")
            
            enhanced_sources.append(enhanced_source)
        
        return enhanced_sources
    
    def extract_tables_from_contexts(
        self,
        contexts: List[Dict],
        format: str = 'html'
    ) -> List[Dict]:
        """
        검색된 컨텍스트에서 표를 추출하여 별도 리스트로 반환
        
        Args:
            contexts: 검색된 컨텍스트 리스트
            format: 변환 형식
        
        Returns:
            표 리스트
                [
                    {
                        "table_id": "t001",
                        "doc_name": "인사규정",
                        "location": "제3장 > 제15조",
                        "html": "<table>...</table>",
                        "markdown": "| ... |"
                    },
                    ...
                ]
        """
        tables = []
        
        for ctx in contexts:
            metadata = ctx.get('metadata', {})
            table_id = metadata.get('table_id')
            
            if table_id and table_id != 'null' and table_id != '':
                doc_name = metadata.get('doc_name', '')
                table_data = self.get_table(doc_name, table_id)
                
                if table_data:
                    table_info = {
                        'table_id': table_id,
                        'doc_name': doc_name,
                        'location': metadata.get('hierarchy_path', ''),
                        'html': self.table_to_html(table_data) if format in ['html', 'both'] else '',
                        'markdown': self.table_to_markdown(table_data) if format in ['markdown', 'both'] else ''
                    }
                    tables.append(table_info)
        
        logger.info(f"총 {len(tables)}개 표 추출 완료")
        return tables


def test_table_processor():
    """TableProcessor 테스트"""
    from pathlib import Path
    
    # 테스트 데이터 생성
    test_dir = Path("test_extracted_results")
    test_doc_dir = test_dir / "extracted_테스트문서"
    test_doc_dir.mkdir(parents=True, exist_ok=True)
    
    # 테스트 표 데이터
    test_tables = {
        "tables": [
            {
                "table_id": "t001",
                "location_hint": "제3장 급여",
                "rows": [
                    {
                        "cells": [
                            {"text": "직급", "colspan": 1, "rowspan": 1},
                            {"text": "기본급", "colspan": 1, "rowspan": 1},
                            {"text": "수당", "colspan": 1, "rowspan": 1}
                        ]
                    },
                    {
                        "cells": [
                            {"text": "과장", "colspan": 1, "rowspan": 1},
                            {"text": "3,500,000원", "colspan": 1, "rowspan": 1},
                            {"text": "300,000원", "colspan": 1, "rowspan": 1}
                        ]
                    }
                ]
            }
        ]
    }
    
    # JSON 파일 저장
    table_file = test_doc_dir / "extracted_테스트문서_표데이터.json"
    with open(table_file, 'w', encoding='utf-8') as f:
        json.dump(test_tables, f, ensure_ascii=False, indent=2)
    
    # TableProcessor 테스트
    processor = TableProcessor(extracted_dir=test_dir)
    
    # 표 로드 테스트
    print("\n=== 표 로드 테스트 ===")
    tables = processor.load_tables_from_doc("테스트문서")
    print(f"로드된 표 수: {len(tables)}")
    
    # HTML 변환 테스트
    print("\n=== HTML 변환 테스트 ===")
    table_data = processor.get_table("테스트문서", "t001")
    if table_data:
        html = processor.table_to_html(table_data)
        print(html)
    
    # Markdown 변환 테스트
    print("\n=== Markdown 변환 테스트 ===")
    if table_data:
        markdown = processor.table_to_markdown(table_data)
        print(markdown)
    
    # 컨텍스트 처리 테스트
    print("\n=== 컨텍스트 처리 테스트 ===")
    test_contexts = [
        {
            "content": "급여는 기본급과 수당을 합산하여 지급한다.",
            "metadata": {
                "doc_name": "테스트문서",
                "table_id": "t001",
                "hierarchy_path": "제3장 > 제15조"
            }
        }
    ]
    
    tables_extracted = processor.extract_tables_from_contexts(test_contexts, format='both')
    print(f"추출된 표 수: {len(tables_extracted)}")
    if tables_extracted:
        print(f"첫 번째 표:")
        print(f"  - table_id: {tables_extracted[0]['table_id']}")
        print(f"  - location: {tables_extracted[0]['location']}")
    
    # 정리
    import shutil
    shutil.rmtree(test_dir)
    print("\n테스트 완료 및 정리 완료")


if __name__ == "__main__":
    test_table_processor()

