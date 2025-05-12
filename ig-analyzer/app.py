import logging
import traceback
import os
import base64
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI
from flask_cors import CORS

# ——— 로깅 설정 ———
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# .env에서 API 키 불러오기
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
assert OPENAI_API_KEY, "OPENAI_API_KEY is required"

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=OPENAI_API_KEY)

# Flask 앱 초기화
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)


def fetch_user_interactions(username: str, limit: int = 5) -> dict:
    """
    Instagram 웹 프로필 JSON API를 이용해 공개 계정(username)의
    최근 limit개 게시물 캡션·좋아요 평균·댓글 수 추출
    """
    interactions = {"recent_posts": [], "avg_likes": 0, "recent_comment_texts": []}
    try:
        UA = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        )
        url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
        headers = {"User-Agent": UA}
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        user = resp.json()["data"]["user"]

        edges = user["edge_owner_to_timeline_media"]["edges"][:limit]
        likes = []
        for edge in edges:
            node = edge["node"]
            # 캡션
            cap_edges = node.get("edge_media_to_caption", {}).get("edges", [])
            text = cap_edges[0]["node"]["text"][:100] if cap_edges else ""
            interactions["recent_posts"].append(text)
            # 좋아요 수
            likes.append(node.get("edge_liked_by", {}).get("count", 0))
            # (댓글은 생략)

        if likes:
            interactions["avg_likes"] = sum(likes) // len(likes)

    except Exception:
        logging.error("Instagram 스크래핑 오류:\n%s", traceback.format_exc())
    return interactions

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"pong": True})

@app.route('/', methods=['GET'])
def home():
    return "SafePost API is running!"

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        caption = data.get("caption", "")
        image_b64 = data.get("image")
        if not image_b64:
            return jsonify({"error": "image missing"}), 400

        prompt = f"""
너는 인스타그램 감성 분석 도우미야.

아래 게시물(이미지+캡션)을 분석해.

🎯 반드시 다음 3가지를 생성해야 해:
1. 사람들이 싫어하지 않을 확률 (0~100 숫자만)
2. 위험도에 대한 짧고 구체적인 경고 메시지
3. 개선을 위한 짧고 구체적인 추천 메시지

응답 포맷:
싫어하지 않을 확률: (숫자)%
경고: (경고 문구)
추천: (추천 문구)

캡션: {caption}
"""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "당신은 인스타그램 감성 분석 도우미입니다. JSON 형식으로만 응답하세요."},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.0,
            max_tokens=300
        )

        raw_text = response.choices[0].message.content.strip()
        logging.debug("analyze 응답: %s", raw_text)
        return jsonify({"result": raw_text})

    except Exception as e:
        tb = traceback.format_exc()
        logging.error("analyze 엔드포인트 오류:\n%s", tb)
        return jsonify({"error": str(e), "traceback": tb}), 500

@app.route('/risk_assess', methods=['OPTIONS'])
def risk_assess_preflight():
    return ('', 200, {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    })

@app.route('/risk_assess', methods=['POST'])
def risk_assess():
    try:
        payload = request.get_json()
        caption = payload.get("caption", "")
        image_b64 = payload.get("image")
        target_id = payload.get("target_user_id")
        if not image_b64 or not target_id:
            return jsonify({"error": "image or target_user_id missing"}), 400

        interactions = fetch_user_interactions(target_id)

        prompt = f"""
너는 인스타 지인 반응 리스크 평가 전문가야.

아래는 대상 지인({target_id})의 최근 활동 내역이야:
- 최근 게시물 요약: {interactions['recent_posts']}
- 평균 좋아요 수: {interactions['avg_likes']}

아래 게시물(이미지+캡션)에 대해:
1) 싫어하지 않을 확률(0~100)%
2) 민감 포인트
3) 공개 범위 추천

반드시 아래 형식으로만 JSON을 반환하세요:
{{
  "싫어하지않을확률": "X%",
  "민감포인트": ["포인트1", "포인트2"],
  "공개범위추천": "전체공개|비공개|친구공개"
}}

캡션: {caption}
"""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 인스타그램 포스트의 팔로워 반응 리스크를 평가하는 도구입니다. "
                        "영어를 사용하지 말고, 키와 값을 모두 한국어로 출력하세요. "
                        "반드시 JSON 형식으로만 응답하세요."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=300
        )

        result = response.choices[0].message.content.strip()
        logging.debug("risk_assess 응답: %s", result)
        return jsonify({"risk_assessment": result})

    except Exception as e:
        tb = traceback.format_exc()
        logging.error("risk_assess 엔드포인트 오류 발생:\n%s", tb)
        return jsonify({"error": str(e), "traceback": tb}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
