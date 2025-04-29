import os
import base64
import re
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI
from flask_cors import CORS

# .env에 있는 API 키 불러오기
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)
CORS(app)

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.json
    caption = data.get("caption", "")
    image_base64 = data.get("image")

    if not image_base64:
        return jsonify({"error": "image missing"}), 400

    try:
        prompt = f"""
너는 인스타그램 감성 분석 도우미야.

아래 게시물(이미지+캡션)을 분석해.

🎯 반드시 다음 3가지를 생성해야 해:
1. 사람들이 싫어하지 않을 확률 (0~100 숫자만)
2. 위험도에 대한 짧고 구체적인 경고 메시지
3. 개선을 위한 짧고 구체적인 추천 메시지

설령 이미지가 흐릿하거나 이해하기 어렵더라도,  
반드시 상상력을 발휘해서 결과를 만들어야 한다.  
"분석할 수 없습니다" 같은 말은 절대 쓰지 말고,  
무조건 확률, 경고, 추천을 출력해.

응답 포맷은 정확히 다음처럼 맞춰야 해:

싫어하지 않을 확률: (숫자)%
경고: (경고 문구)
추천: (추천 문구)

(아래 게시물 분석 시작)

캡션: {caption}
"""


        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=300
        )

        raw_text = response.choices[0].message.content.strip()
        print("GPT 원본 응답:", raw_text)


        return jsonify({"result": raw_text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
