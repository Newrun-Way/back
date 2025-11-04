#!/usr/bin/env python3
"""
간단한 HWP/HWPX 파싱 테스트
"""
import requests
import json
import time
from pathlib import Path

def simple_test():
    """간단한 테스트 함수"""
    base_url = "http://localhost:8000"
    api_url = f"{base_url}/api/v1/parsing/upload-and-parse/"
    target_dir = Path("temp_uploads")

    print("🚀 간단 파싱 테스트")
    print("=" * 50)

    # 서버 확인
    try:
        health = requests.get(f"{base_url}/api/v1/health")
        if health.status_code != 200:
            print("❌ 서버 응답 없음")
            return
        print("✅ 서버 정상")
    except:
        print("❌ 서버 연결 실패")
        return

    # 파일 테스트
    files = list(target_dir.glob("*.hwp")) + list(target_dir.glob("*.hwpx"))

    if not files:
        print("❌ 테스트 파일 없음")
        return

    for file_path in files:
        print(f"\n📁 {file_path.name}")
        print("-" * 30)

        start = time.time()

        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = requests.post(api_url, files=files)

            end = time.time()

            if response.status_code == 200:
                data = response.json()
                parsed = data['parsed_data']

                print(f"✅ 성공 ({end-start:.3f}초)")
                print(f"   타입: {parsed['file_type']}")
                print(f"   텍스트: {len(parsed['text_content'])}개")
                print(f"   표: {len(parsed['tables'])}개")
                print(f"   이미지: {len(parsed['images'])}개")

                # 텍스트 미리보기
                if parsed['text_content']:
                    preview = parsed['text_content'][0][:50]
                    print(f"   미리보기: {preview}...")

            else:
                print(f"❌ 실패 ({response.status_code})")
                print(f"   {response.text}")

        except Exception as e:
            print(f"❌ 에러: {e}")

if __name__ == "__main__":
    simple_test()