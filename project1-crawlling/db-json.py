from pymongo import MongoClient
import json

# ✅ MongoDB 연결 정보
mongo_uri = "mongodb+srv://dataEngineering:0000@cluster0.naylo.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(mongo_uri)
db = client["dataEngineering"]
collection = db["Agoda_jeju"]

# ✅ MongoDB에서 모든 문서 불러오기
docs = list(collection.find())

# ✅ ObjectId 제거 + 리뷰 5개만 자르기
for doc in docs:
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if "reviews" in doc and isinstance(doc["reviews"], list):
        doc["reviews"] = doc["reviews"]

# ✅ 파일로 저장
with open("../project1/agoda_mongo_export.json", "w", encoding="utf-8") as f:
    json.dump(docs, f, ensure_ascii=False, indent=2)

print(f"✅ 총 {len(docs)}개의 호텔 데이터가 'agoda_mongo_export.json' 파일로 저장되었습니다.")
