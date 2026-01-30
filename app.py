import os
import json
import time

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
channel_names = json.loads(os.getenv("CHANNEL_NAMES", "{}"))
channel_ids = list(channel_names.keys())

for cid in channel_ids:
    name = channel_names.get(cid)
    # 이제 cid와 name을 둘 다 쓸 수 있음!
print(f"🔍 설정 확인: 총 {len(channel_ids)}개의 채널 ID를 로드했습니다.")
print(f"📋 채널 목록: {list(channel_names.values())}")

slack_client = WebClient(token=SLACK_TOKEN)
notion_client = Client(auth=NOTION_TOKEN)

# 1.5 사용자 목록 가져오기 (ID -> 본명 매핑용)
def fetch_user_map(client):
    """슬랙 워크스페이스의 모든 사용자 정보를 가져와 {ID: Real Name} 맵 생성"""
    user_map = {}
    try:
        cursor = None
        while True:
            response = client.users_list(cursor=cursor, limit=100)
            if not response['ok']:
                break
            
            for user in response['members']:
                uid = user['id']
                # real_name이 없으면 name(아이디) 사용
                real_name = user.get('real_name') or user.get('name') or uid
                user_map[uid] = real_name
            
            cursor = response.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break
        
        print(f"👥 사용자 매핑 완료: 총 {len(user_map)}명")
        return user_map
    except Exception as e:
        print(f"⚠️ 사용자 목록 가져오기 실패: {e}")
        return {}

USER_MAP = fetch_user_map(slack_client)

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

        # 사용자 ID를 이름으로 치환
        for msg in final_data:
            if 'user' in msg:
                uid = msg['user']
                msg['user'] = USER_MAP.get(uid, uid)  # 매핑된 이름이 없으면 ID 그대로 사용

        # 파일 저장
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
        
        print(f"   💾 저장 완료: {file_name} (총 {len(final_data)}개 메시지)")
        return file_name
    except Exception as e:
        print(f"   ❌ [{cname}] 수집 실패: {e}")
        return None

# 2. 채널별 루프
for i, cid in enumerate(channel_ids):
    name = channel_names.get(cid, cid)
    print(f"\n🔄 전체 진행률: {i+1}/{len(channel_ids)} ({name})")
    
    path = collect_and_save(cid, name)
    time.sleep(5)

print("\n🚀 모든 작업이 끝났습니다! 노션과 폴더 내 JSON 파일들을 확인하세요.")
time.sleep(2)
print("\n🚀 이제 llm 돌린다잉!.")

os.system("python llm.py")