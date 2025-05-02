import openai
from pymongo import MongoClient
import re
import os

# ✅ OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")

# ✅ MongoDB 연결
mongo_uri = "mongodb+srv://dataEngineering:0000@cluster0.naylo.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(mongo_uri)
db = client["dataEngineering"]
collection = db["Agoda_jeju"]

# ✅ 프롬프트
base_prompt = """
입력된 텍스트는 숙소, 식당, 관광지에 대한 리뷰입니다.
주어진 리뷰 텍스트에서 주요한 키워드들을 최대 10개까지만 추출하여 정리하세요.
각 키워드에 대해 다음 세 가지 정보를 추출해주세요:

1. 카테고리명 (예: 방, 음식, 서비스, 위치, 편의시설 등)
2. 키워드 (명사, 하나의 단어로 구성)
3. 감성 (긍정 / 부정 / 중립)

요구사항:
- 키워드는 하나의 명사 단어로 구성되어야 합니다.
- 의미가 모호하거나 추상적인 단어는 제외합니다.
- 감성은 '긍정', '부정', '중립' 중 하나로 판단합니다.
- 중요도 순으로 정렬해주세요.

출력 형식:
[카테고리명]
키워드1 - 감성
키워드2 - 감성

출력 형식에 번호는 필요 없습니다.
"""

# ✅ GPT 분석 함수
def analyze_review_with_gpt(content):
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "너는 리뷰에서 키워드, 감성, 카테고리를 추출하는 분석 도우미야."},
                {"role": "user", "content": base_prompt + "\n\n" + content}
            ],
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        print("❌ GPT 오류:", e)
        return None

# ✅ 분석 결과 파싱 함수
def parse_analysis_result(text):
    result = []
    current_category = None
    for line in text.strip().split("\n"):
        cat_match = re.match(r"\[(.+?)\]", line)
        if cat_match:
            current_category = cat_match.group(1).strip()
        elif "-" in line and current_category:
            try:
                keyword, sentiment = line.strip().split(" - ")
                result.append({
                    "category": current_category,
                    "keyword": keyword.strip(),
                    "sentiment": sentiment.strip()
                })
            except:
                continue
    return result

# ✅ 리뷰 단위로 처리 및 저장
for doc in collection.find():
    doc_id = doc["_id"]
    reviews = doc.get("reviews", [])

    for idx, review in enumerate(reviews):
        if "keywords_analysis" in review:
            continue

        content = review.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        content = content.strip()

        print(f"\n🔍 [문서 ID: {doc_id}] 리뷰 {idx+1}: {content[:60]}...")

        gpt_result = analyze_review_with_gpt(content)
        if gpt_result:
            parsed = parse_analysis_result(gpt_result)

            # ✅ 해당 리뷰 위치에 결과 저장
            collection.update_one(
                {"_id": doc_id},
                {f"$set": {f"reviews.{idx}.keywords_analysis": parsed}}
            )

            # ✅ 콘솔 출력
            print("📌 키워드 분석 결과:")
            for item in parsed:
                print(f"  ▸ [{item['category']}] {item['keyword']} - {item['sentiment']}")

            print(f"✅ 리뷰 {idx+1} 저장 완료")
