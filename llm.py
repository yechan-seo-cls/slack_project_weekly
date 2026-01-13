import json
import ollama
import os
import time
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client
import shutil

load_dotenv()

# 1. 설정 로드
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
notion = Client(auth=NOTION_TOKEN)

# 채널 ID 및 이름 매핑 로드
raw_ids = os.getenv("CHANNEL_IDS", "")
channel_ids = [cid.strip() for cid in raw_ids.split(",") if cid.strip()]
channel_names = json.loads(os.getenv("CHANNEL_NAMES", "{}"))

def get_summary_title():
    """현재 날짜 기준 'X월 X주차 요약' 제목 생성"""
    now = datetime.now()
    month_week = (now.day - 1) // 7 + 1
    return f"{now.month}월 {month_week}주차 업무 요약 ({now.strftime('%Y-%m-%d')})"

def summarize_with_local_llm(file_path):
    """JSON 파일을 읽어 로컬 LLM으로 요약"""
    if not os.path.exists(file_path):
        print(f"파일을 찾을 수 없음: {file_path}")
        return None

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    context_text = ""
    for msg in data[:200]: # 너무 길면 상위 200개만
        user = msg.get('user', 'User')
        text = msg.get('text', '')
        if text.strip():
            if msg.get('thread_ts') and msg.get('thread_ts') != msg.get('ts'):
                context_text += f"  - [댓글][{user}]: {text}\n"
            else:
                context_text += f"\n[{user}]: {text}\n"

    prompt = f"""
    너는 사내 메시지 분석 전문가야. 아래의 슬랙 대화 내용을 읽고 요약해줘.
    반드시 한국어로 작성하고, '뭐뭐했습니다' 대신 '뭐뭐함' 식의 깔끔한 개조식 표현을 써줘.

    [요약 형식]
    1. 주요 흐름: 전체적인 상황 요약
    2. 논의 사항: 주요 논의 내용과 결과
    3. 결정사항 및 할 일: 확정된 내용 및 후속 조치

    대화 내용:
    {context_text}
    """

    print(f"🤖 {file_path} 요약 시작...")
    response = ollama.chat(
        model='llama3.1',
        messages=[
            {'role': 'system', 'content': '너는 유능한 비서야.'},
            {'role': 'user', 'content': prompt},
        ]
    )
    return response['message']['content']

def create_main_page(database_id):
    """노션 DB에 '이번 주차 메인 페이지'를 하나 생성하고 ID 반환"""
    try:
        new_page = notion.pages.create(
            parent={"database_id": database_id},
            properties={
                "이름": {"title": [{"text": {"content": get_summary_title()}}]},
            }
        )
        print(f"📝 메인 페이지 생성 완료: {get_summary_title()}")
        return new_page["id"]
    except Exception as e:
        print(f"메인 페이지 생성 실패: {e}")
        return None

def add_channel_toggle(page_id, channel_name, summary_text):
    """메인 페이지 내부에 채널별 토글 추가 (에러 수정 버전)"""
    try:
        notion.blocks.children.append(
            block_id=page_id,
            children=[
                {
                    "object": "block",
                    "type": "toggle",
                    "toggle": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": f"📂 {channel_name} 채널 요약"},
                                "annotations": {"bold": True, "color": "blue"}
                            }
                        ],
                        "children": [
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [{"type": "text", "text": {"content": summary_text[:2000]}}]
                                }
                            }
                        ]
                    }
                }
            ]
        )
        print(f"✅ {channel_name} 토글 추가 완료")
    except Exception as e:
        print(f"❌ {channel_name} 토글 추가 실패: {e}")

def cleanup_json_files(date_str):
    """분석이 끝난 JSON 파일들을 dump 폴더로 이동"""
    dump_dir = "./dump"
    if not os.path.exists(dump_dir):
        os.makedirs(dump_dir)
        print(f"📂 폴더 생성: {dump_dir}")

    count = 0
    # 현재 폴더의 모든 파일을 검사
    for file in os.listdir("."):
        # 오늘 날짜(date_str)가 포함된 JSON 파일 찾기
        if file.endswith(f"{date_str}.json") and file.startswith("history_"):
            source = os.path.join(".", file)
            destination = os.path.join(dump_dir, file)
            
            # 파일 이동 (이미 있으면 덮어씀)
            shutil.move(source, destination)
            print(f"📦 이동 완료: {file} -> {dump_dir}")
            count += 1
    
    return count

# --- 메인 실행부 ---
if __name__ == "__main__":
    # 1. 이번 주차 통합 페이지 딱 하나 생성
    parent_page_id = create_main_page(DATABASE_ID)
    date_str = datetime.now().strftime('%m%d')

    if parent_page_id:
            # 2. .env에서 가져온 리스트 순회
            for cid in channel_ids:
                cid = cid.strip()
                
                # [핵심] CHANNEL_NAMES 딕셔너리에서 ID(Key)를 넣어 이름(Value)을 가져옴
                # 예: channel_names["C03LN2U7TQE"] -> "KNLCS"
                display_name = channel_names.get(cid, cid) 
                
                # 파일명은 이미지처럼 ID 기반으로 설정
                file_name = f"history_{cid}_{date_str}.json" 
                
                print(f"\n🔍 분석 중: {file_name} (표시 이름: {display_name})")
                
                # 요약 진행
                summary_result = summarize_with_local_llm(file_name)
                
                if summary_result:
                    # 3. 노션 토글 추가 (ID가 아닌 display_name을 전달)
                    add_channel_toggle(parent_page_id, display_name, summary_result)
                    time.sleep(0.5) 

    print("\n✨ 모든 채널의 요약본이 노션에 매핑된 이름으로 업로드되었습니다!")