import os
import json
from dotenv import load_dotenv
from slack_sdk import WebClient

load_dotenv()
SLACK_TOKEN = os.getenv("SLACK_TOKEN")
client = WebClient(token=SLACK_TOKEN)

try:

    response = client.users_list()
    if response['ok']:
        print("✅ 사용자 목록 가져오기 성공!")
        found = False
        target_uid = "U59D7KLSD"
        for user in response['members']:
            if user['id'] == target_uid:
                print(f"🎯 Found target user {target_uid}: {user.get('real_name')} / {user.get('name')}")
                found = True
                break
        if not found:
            print(f"❌ User {target_uid} NOT found in the list.")
    else:
        print(f"❌ API 호출 실패: {response['error']}")
except Exception as e:
    print(f"❌ 예외 발생: {e}")
