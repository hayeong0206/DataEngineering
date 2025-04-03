from pymongo import MongoClient

# ✅ MongoDB 연결
mongo_uri = "mongodb+srv://dataEngineering:0000@cluster0.naylo.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(mongo_uri)
db = client["dataEngineering"]
collection = db["Agoda_jeju"]

# ✅ 전체 삭제
result = collection.delete_many({})
print(f"🧹 삭제된 문서 수: {result.deleted_count}")