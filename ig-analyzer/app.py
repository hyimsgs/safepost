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
OPENAI_API_KEY         = os.getenv("OPENAI_API_KEY")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
GRAPH_API_URL          = "https://graph.instagram.com"

# 필수 환경변수 검증
assert OPENAI_API_KEY, "OPENAI_API_KEY is required"
assert INSTAGRAM_ACCESS_TOKEN, "INSTAGRAM_ACCESS_TOKEN is required"

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)
# 모든 엔드포인트에 대해 CORS 허용, OPTIONS 프리플라이트도 처리
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)


def fetch_user_interactions(user_id: str, limit: int = 5) -> dict:
    """
    Instagram Graph API로 특정 유저(user_id)의
    최근 게시물 캡션(요약), 평균 좋아요 수, 해당 유저가 단 댓글 텍스트를 가져옵니다.
    """
    interactions = {
        "recent_posts": [],
        "avg_likes": 0,
        "recent_comment_texts": []
    }

    try:
        # 1) 유저의 최근 미디어 목록 조회
        resp = requests.get(
            f"{GRAPH_API_URL}/{user_id}/media",
            params={
                "fields": "id,caption,like_count",
                "access_token": INSTAGRAM_ACCESS_TOKEN,
                "limit": limit
            }
        )
        resp.raise_for_status()
        media_list = resp.json().get("data", [])

        likes = []
        for m in media_list:
            post_id = m["id"]
            cap = m.get("caption", "")
            # 캡션은 최대 100자까지만 저장
            interactions["recent_posts"].append(cap[:100])
            likes.append(m.get("like_count", 0))

            # 2) 댓글 조회 (username,text 포함)
            c_resp = requests.get(
                f"{GRAPH_API_URL}/{post_id}/comments",
                params={
                    "fields": "username,text",
                    "access_token": INSTAGRAM_ACCESS_TOKEN,
                    "limit": 10
                }
            )
            c_resp.raise_for_status()
            for c in c_resp.json().get("data", []):
                if c.get("username") == user_id:
                    interactions["recent_comment_texts"].append(c.get("text", ""))

        # 평균 좋아요 수 계산
        if likes:
            interactions["avg_likes"] = int(sum(likes) / len(likes))

    except Exception:
        logging.error("Instagram API 호출 오류:\n%s", traceback.format_exc())

    return interactions
@app.route('/ping', methods=['GET'])
@app.route('/ping/', methods=['GET'])
def ping():
    return jsonify({"pong": True})


@app.route("/", methods=["GET"])
def home():
    return "SafePost API is running!"


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json()
        caption   = data.get("caption", "")
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
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
                    }
                ]
            }],
            max_tokens=300
        )

        raw_text = response.choices[0].message.content.strip()
        logging.debug("analyze 응답: %s", raw_text)
        return jsonify({"result": raw_text})

    except Exception as e:
        tb = traceback.format_exc()
        logging.error("analyze 엔드포인트 오류:\n%s", tb)
        return jsonify({"error": str(e), "traceback": tb}), 500
    
    


# ① OPTIONS 프리플라이트 전용 핸들러
@app.route("/risk_assess", methods=["OPTIONS"])
def risk_assess_preflight():
    return ("", 200, {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })


# ② 실제 POST 핸들러
@app.route("/risk_assess", methods=["POST"])
def risk_assess():
    try:
        payload   = request.get_json()
        caption   = payload.get("caption", "")
        image_b64 = payload.get("image")
        target_id = payload.get("target_user_id")
        print(">>> BACKEND RESPONSE:", result)


        if not image_b64 or not target_id:
            return jsonify({"error": "image or target_user_id missing"}), 400

        interactions = fetch_user_interactions(target_id)

        prompt = f"""
너는 인스타 지인 리스크 평가 전문가야.

아래는 대상 지인({target_id})의 최근 활동 내역이야:
- 최근 게시물 요약: {interactions['recent_posts']}
- 평균 좋아요 수: {interactions['avg_likes']}
- 지인이 단 최근 댓글 예시: {interactions['recent_comment_texts'] or '없음'}

아래 게시물(이미지+캡션)에 대해:
1) 싫어할 확률(0~100)%,
2) 민감 포인트,
3) 공개 범위 추천

응답 포맷:
싫어할 확률: (숫자)%
민감 포인트: (문장)
공개 범위 추천: (문장)

캡션: {caption}
"""

        response = client.chat.completions.create(
    model="gpt-4o",
    # 이미지는 multimodal_inputs로 분리
    multimodal_inputs=[{
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
    }],
    # system + user 메시지
    messages=[
        {
            "role": "system",
            "content": (
                "당신은 인스타그램 포스트의 팔로워 반응 리스크를 평가하는 도구입니다. "
                "반드시 아래 JSON 스키마만 반환하세요:\n"
                "{\n"
                '  "risk_assessment": "싫어할 확률: X%",\n'
                '  "sensitive_points": ["포인트1", "포인트2"],\n'
                '  "visibility_recommendation": "public|private|close_friends"\n'
                "}"
            )
        },
        {
            "role": "user",
            "content": (
                f"다음 이미지를 보고, 캡션 \"{caption}\"과 함께:\n"
                "- 팔로워가 싫어할 확률을 % 단위로\n"
                "- 민감 포인트 목록\n"
                "- 공개 범위 추천\n"
                "형식 그대로 JSON으로만 응답해주세요."
            )
        }
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
    # app.py 맨 아래에 추가
@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"pong": True})

