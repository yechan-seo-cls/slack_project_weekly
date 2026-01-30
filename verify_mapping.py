import os
import json
from dotenv import load_dotenv
from slack_sdk import WebClient
import time
from datetime import datetime, timedelta

load_dotenv()
SLACK_TOKEN = os.getenv("SLACK_TOKEN")
slack_client = WebClient(token=SLACK_TOKEN)

# 1. Fetch User Map
print("👥 사용자 목록 가져오는 중...")
user_map = {}
try:
    cursor = None
    while True:
        response = slack_client.users_list(cursor=cursor, limit=100)
        if not response['ok']:
            break
        
        for user in response['members']:
            uid = user['id']
            real_name = user.get('real_name') or user.get('name') or uid
            user_map[uid] = real_name
        
        cursor = response.get('response_metadata', {}).get('next_cursor')
        if not cursor:
            break
    print(f"✅ 매핑 완료: {len(user_map)}명")
except Exception as e:
    print(f"❌ 매핑 실패: {e}")

# 2. Collect from one channel (KNLCS - C83M8CWRX from previous logs)
target_cid = "C83M8CWRX" 
target_cname = "KNLCS"

print(f"\n📡 [{target_cname}] 메시지 수집 및 매핑 테스트...")
try:
    now = datetime.now()
    oldest_ts = time.mktime((now - timedelta(days=7)).timetuple())
    
    result = slack_client.conversations_history(channel=target_cid, oldest=str(oldest_ts), limit=5)
    messages = result.data['messages']
    
    print(f"🔍 {len(messages)}개 메시지 확인:")
    for i, msg in enumerate(messages):
        original_uid = msg.get('user', 'Unknown')
        mapped_name = user_map.get(original_uid, original_uid)
        print(f"[{i+1}] ID: {original_uid} -> Name: {mapped_name}")
        
        # Verify if mapping actually happened (assuming mapped name is not starting with U and length > 9 if it was an ID)
        if original_uid.startswith("U") and mapped_name != original_uid:
             print(f"   ✨ 매핑 성공!")
        elif original_uid == mapped_name:
             print(f"   ⚠️ 매핑 안됨 (또는 봇/시스템 메시지)")

except Exception as e:
    print(f"❌ 테스트 실패: {e}")
