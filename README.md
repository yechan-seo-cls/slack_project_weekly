# Slack-Project_weekly

이 프로젝트는 매주 Slack의 project 채널에서의 대화를 요약해 노션에 전달해주는 시스템입니다.

## 🚀 프로젝트 구조

- `app.py': 각 채널을 순회해 메시지를 json으로 저장해주는 역할을 수행합니다.
- `llm.py`: app.py를 통해 생성된 json을 LLM에게 전달해 요약본을 생성 후 노션 DataBase에 해당 내용을 업로드합니다.
- 'verify_mapping.py & Verify_permissions.py': 실제 user name을 추출하는 역할을 수행합니다.

## 🛠 환경 구성

1. pip install -r requirements.txt 수행해 구동에 필요한 라이브러리를 다운 받습니다.
2. .env 파일에 각종 인증 토큰 정보를 넣습니다. sample.env를 참고하세요.
3. llm.py의 api_key_path에 GPT API 토큰의 경로를 입력합니다.
