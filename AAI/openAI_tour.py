import openai
import random
import json
import re
from pymongo import MongoClient
from bson import ObjectId
from tqdm import tqdm  # ✅ 진행률 표시용 라이브러리

# ✅ MongoDB 연결
client = MongoClient("mongodb+srv://dataEngineering:0000@cluster0.naylo.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client["dataEngineering"]
collection = db["Agoda_jeju"]  # 예시: 호텔

# ✅ OpenAI 설정
openai.api_key = "your_api_key"

# ✅ base prompt
base_prompt = """
다음은 관광지 리뷰입니다. 리뷰에서 10개 미만의 핵심 키워드를 뽑고, 카테고리와 감성(긍정/부정/중립)을 정리해주세요. 외국어의 경우 한국어로 번역해주세요.
출력 형식:
[카테고리]
키워드 - 감성
"""

# ✅ GPT 호출 함수
def analyze_review_with_gpt(content):
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "리뷰 키워드 감성 분석 도우미"},
                {"role": "user", "content": base_prompt + "\n\n" + content}
            ],
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        print("❌ GPT 오류:", e)
        return None

# ✅ 응답 파싱 함수
def parse_analysis_result(text):
    result = []
    current_category = None
    for line in text.strip().split("\n"):
        if "[" in line and "]" in line:
            current_category = line.strip("[]")
        elif "-" in line and current_category:
            try:
                keyword, sentiment = line.split(" - ")
                result.append({
                    "category": current_category.strip(),
                    "keyword": keyword.strip(),
                    "sentiment": sentiment.strip()
                })
            except:
                continue
    return result

# ✅ STEP 1: 유효한 리뷰만 수집 (20자 이상, 미분석)
sample_file = "sampled_reviews.json"

try:
    with open(sample_file, "r", encoding="utf-8") as f:
        sampled_reviews = json.load(f)
    print(f"📂 기존 샘플 파일 불러오기 완료: {len(sampled_reviews)}개")

except FileNotFoundError:
    print("📤 샘플 파일이 없어 새로 샘플링합니다...")
    all_review_targets = []
    for doc in collection.find():
        for idx, review in enumerate(doc.get("reviews", [])):
            content = review.get("content")
            already_done = "keywords_analysis" in review

            if not already_done and isinstance(content, str) and len(content.strip()) >= 20:
                all_review_targets.append({
                    "_id": str(doc["_id"]),
                    "review_index": idx,
                    "content": content.strip()
                })

    total = len(all_review_targets)
    sample_size = int(total * 0.15)
    sampled_reviews = random.sample(all_review_targets, sample_size)

    with open(sample_file, "w", encoding="utf-8") as f:
        json.dump(sampled_reviews, f, ensure_ascii=False, indent=2)
    print(f"✅ {sample_size}개의 리뷰를 샘플링하고 파일로 저장했습니다.")

# ✅ STEP 2: GPT 분석 및 DB 저장
for review_info in tqdm(sampled_reviews, desc="리뷰 분석 진행중"):
    _id = review_info["_id"]
    idx = review_info["review_index"]
    content = review_info["content"]

    # 이미 분석된 경우 스킵
    doc = collection.find_one({"_id": ObjectId(_id)})
    if doc and "keywords_analysis" in doc["reviews"][idx]:
        continue

    print(f"\n📝 리뷰 분석 중: {content[:60]}...")

    gpt_output = analyze_review_with_gpt(content)
    if gpt_output:
        parsed_result = parse_analysis_result(gpt_output)

        # 콘솔에 분석 결과 출력
        print("🔍 분석 결과:")
        for item in parsed_result:
            print(f" - [{item['category']}] {item['keyword']} ({item['sentiment']})")

        # DB에 저장
        collection.update_one(
            {"_id": ObjectId(_id)},
            {"$set": {f"reviews.{idx}.keywords_analysis": parsed_result}}
        )
        print(f"✅ 저장 완료 (index {idx})")
