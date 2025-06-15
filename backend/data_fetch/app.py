"""
app.py  ─ Flask + MongoDB backend with:
  • /api/news          → capped text/date/keyword query (≤2 000 docs)
  • /api/vector_search → semantic search via Atlas Vector Search + SBERT

Environment vars expected:
  MONGO_URI            Atlas cluster URI
  HF_TOKEN             HuggingFace auth (optional but recommended)
  VECTOR_INDEX_NAME    Atlas vector index name   (default: vector_index)
"""
import os, json
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient, errors as pymongo_errors
from bson import json_util
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from huggingface_hub import login

load_dotenv()

# ──────────────── ENV & CONSTANTS ─────────────────────────────────────────────
MONGO_URI          = os.getenv("MONGO_URI")
HF_TOKEN           = os.getenv("HF_TOKEN")
VECTOR_INDEX_NAME  = os.getenv("VECTOR_INDEX_NAME", "vector_index")

DB_NAME            = "news_database"
COLLECTION_NAME    = "articles"          # <- adjust if your collection differs
MAX_RESULTS_LIMIT  = 2_000               # hard cap for /api/news
VECTOR_LIMIT       = 500                 # default limit for /api/vector_search
VECTOR_CANDIDATES  = 2_000               # numCandidates should exceed limit

# ──────────────── FLASK APP ───────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ──────────────── EMBEDDING MODEL ─────────────────────────────────────────────
embedding_model = None
try:
    if HF_TOKEN:
        login(token=HF_TOKEN)
    print("Loading SentenceTransformer (all-mpnet-base-v2)…")
    embedding_model = SentenceTransformer("all-mpnet-base-v2")
    print("✅  SentenceTransformer ready.")
except Exception as e:
    print("❌  Could not load embedding model:", e)

def embed(text: str):
    """Return list[float] or None."""
    if not embedding_model:
        return None
    try:
        return embedding_model.encode(text).tolist()
    except Exception as exc:
        print("Embedding error:", exc)
        return None

# ──────────────── MONGODB ─────────────────────────────────────────────────────
client = None
collection = None
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4_000)
    client.admin.command("ping")
    collection = client[DB_NAME][COLLECTION_NAME]
    print(f"✅  Mongo connected • DB={DB_NAME} • Col={COLLECTION_NAME}")
except Exception as e:
    print("❌  Mongo connection failed:", e)

# ──────────────── COMMON HELPERS ──────────────────────────────────────────────
PROJECTION = {
    "_id": 1, "title": 1, "summary": 1, "url": 1,
    "latitude": 1, "longitude": 1, "SQLDATE": 1, "SOURCEURL": 1
}
def _j(d):
    """BSON-safe JSON response."""
    return json.loads(json_util.dumps(d))

# ──────────────── ROUTES ──────────────────────────────────────────────────────
@app.route("/api/news")
def api_news():
    if collection is None:
        return jsonify({"error": "DB not ready"}), 503

    # ---------- query params ----------
    q   = request.args.get("q")
    frm = request.args.get("from")
    to  = request.args.get("to")
    limit_req = request.args.get("limit", type=int) or MAX_RESULTS_LIMIT
    limit = min(max(limit_req, 100), MAX_RESULTS_LIMIT)

    # ---------- aggregation pipeline ----------
    pipe = []

    if q:
        pipe += [
            {"$search": {
                "index": "default",
                "text": {"path": {"wildcard": "*"}, "query": q}
            }},
            {"$addFields": {"score": {"$meta": "searchScore"}}},
            {"$sort": {"score": -1}}
        ]

    match = {"latitude": {"$ne": None}, "longitude": {"$ne": None}}
    if frm or to:
        date_range = {}
        if frm: date_range["$gte"] = frm
        if to:  date_range["$lte"] = to
        match["SQLDATE"] = date_range
    pipe.append({"$match": match})

    pipe.append({"$project": PROJECTION})
    pipe.append({"$limit": limit})

    # ---------- run ----------
    try:
        docs = list(collection.aggregate(pipe))
        return _j({
            "results": docs,
            "count": len(docs),
            "limit_applied": len(docs) >= limit
        })
    except pymongo_errors.OperationFailure as e:
        return jsonify({"error": e.details.get("errmsg", str(e))}), 500

@app.route("/api/vector_search")
def api_vector():
    if collection is None or embedding_model is None:
        return jsonify({"error": "Service not ready"}), 503

    q  = request.args.get("q")
    if not q:
        return jsonify({"error": "Missing ?q"}), 400

    limit = request.args.get("limit", type=int) or VECTOR_LIMIT
    limit = min(max(limit, 50), VECTOR_LIMIT)   # clamp 50-500

    vec = embed(q)
    if vec is None:
        return jsonify({"error": "Embedding failed"}), 500

    pipe = [
        {"$vectorSearch": {
            "index": VECTOR_INDEX_NAME,
            "path": "summary_embedding",        # field holding your vectors
            "queryVector": vec,
            "numCandidates": max(VECTOR_CANDIDATES, limit * 4),
            "limit": limit
        }},
        {"$project": {**PROJECTION, "score": {"$meta": "vectorSearchScore"}}},
        {"$match": {"score": {"$gt": 0.7}}}      # similarity threshold
    ]

    try:
        docs = list(collection.aggregate(pipe))
        return _j({"results": docs, "count": len(docs), "limit_applied": None})
    except pymongo_errors.OperationFailure as e:
        msg = e.details.get("errmsg", str(e))
        if "index not found" in msg.lower():
            msg += f" — check VECTOR_INDEX_NAME='{VECTOR_INDEX_NAME}' in Atlas."
        return jsonify({"error": msg}), 500

# ──────────────── MAIN ────────────────────────────────────────────────────────
if __name__ == "__main__":
    ready = client is not None and embedding_model is not None
    if not ready:
        print("Backend cannot start: DB or embedding model missing.")
    else:
        app.run(host="0.0.0.0", port=5001, debug=False)
