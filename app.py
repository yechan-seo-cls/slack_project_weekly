import os
import json
import time
import ollama
from datetime import datetime, timedelta
from dotenv import load_dotenv
from slack_sdk import WebClient
from notion_client import Client

load_dotenv()

# 1. 초기 설정 및 디버깅 로그
SLACK_TOKEN = os.getenv("SLACK_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

# 채널 ID 리스트 파싱 (공백 제거)
raw_ids = os.getenv("CHANNEL_IDS", "")
channel_ids = [cid.strip() for cid in raw_ids.split(",") if cid.strip()]
channel_names = json.loads(os.getenv("CHANNEL_NAMES", "{}"))

print(f"🔍 설정 확인: 총 {len(channel_ids)}개의 채널 ID를 로드했습니다.")
print(f"📋 채널 목록: {list(channel_names.values())}")

slack_client = WebClient(token=SLACK_TOKEN)
notion_client = Client(auth=NOTION_TOKEN)

now = datetime.now()
oldest_ts = time.mktime((now - timedelta(days=7)).timetuple())

def collect_and_save(cid, cname):
    """채널별 메시지 수집 및 고유 JSON 저장"""
    # 파일명에 채널 이름을 넣어 중복 방지
    file_name = f"history_{cname}_{now.strftime('%m%d')}.json"
    print(f"\n📡 [{cname}] 데이터 수집 시작 (ID: {cid})")
    
    try:
        # 메인 메시지 수집
        result = slack_client.conversations_history(channel=cid, oldest=str(oldest_ts))
        messages = result.data['messages']
        
        final_data = []
        print(f"   ㄴ 메인 메시지 {len(messages)}개 발견. 스레드 수집 중...")
        
        for msg in messages:
            final_data.append(msg)
            if 'thread_ts' in msg and msg.get('reply_count', 0) > 0:
                if msg['ts'] == msg['thread_ts']: # 부모 메시지인 경우만
                    replies = slack_client.conversations_replies(channel=cid, ts=msg['ts'])
                    final_data.extend(replies.data['messages'][1:])
                    time.sleep(0.1)

        # 파일 저장
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
        
        print(f"   💾 저장 완료: {file_name} (총 {len(final_data)}개 메시지)")
        return file_name
    except Exception as e:
        print(f"   ❌ [{cname}] 수집 실패: {e}")
        return None

def summarize(file_path):
    """로컬 LLM 요약"""
    print(f"🤖 LLM 요약 중: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not data: return "대화 내용 없음"

    context = ""
    for m in data[:100]: # 너무 길면 LLM이 힘들어하니 최근 100개만
        context += f"[{m.get('user', 'User')}]: {m.get('text', '')}\n"

    response = ollama.chat(model='llama3.1', messages=[
        {'role': 'system', 'content': '사내 업무 요약 비서야. 불렛포인트로 핵심만 요약해.'},
        {'role': 'user', 'content': f"다음 대화를 한국어로 요약해줘:\n{context}"}
    ])
    return response['message']['content']

def create_notion_page(title):
    print(f"📝 노션 페이지 생성 중: {title}")
    new_page = notion_client.pages.create(
        parent={"database_id": DATABASE_ID},
        properties={"이름": {"title": [{"text": {"content": title}}]}}
    )
    return new_page["id"]

def add_to_notion(page_id, cname, summary):
    try:
        notion_client.blocks.children.append(
            block_id=page_id,
            children=[{
                "object": "block",
                "type": "toggle",
                "toggle": {
                    "rich_text": [{
                        "type": "text", 
                        "text": {"content": f"📂 {cname} 채널 요약"},
                        "annotations": {"bold": True, "color": "blue"}
                    }],
                    "children": [{
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"type": "text", "text": {"content": summary[:2000]}}]}
                    }]
                }
            }]
        )
        print(f"   ✅ 노션 토글 추가 성공: {cname}")
    except Exception as e:
        print(f"   ❌ 노션 토글 실패 ({cname}): {e}")

# --- 실행부 ---
month_week = (now.day - 1) // 7 + 1
week_title = f"{now.month}월 {month_week}주차 업무 요약 ({now.strftime('%Y-%m-%d')})"

# 1. 노션 메인 페이지 하나 생성
main_page_id = create_notion_page(week_title)

# 2. 채널별 루프 (여기서 9번 돌아야 함!)
for i, cid in enumerate(channel_ids):
    name = channel_names.get(cid, cid)
    print(f"\n🔄 전체 진행률: {i+1}/{len(channel_ids)} ({name})")
    
    path = collect_and_save(cid, name)
    if path:
        summary_result = summarize(path)
        add_to_notion(main_page_id, name, summary_result)
        time.sleep(1) # API 안정성을 위한 휴식

print("\n🚀 모든 작업이 끝났습니다! 노션과 폴더 내 JSON 파일들을 확인하세요.")