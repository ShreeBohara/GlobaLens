from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient, errors as pymongo_errors
from bson import json_util
import json
import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from huggingface_hub import login

# --- Configuration & Initialization ---
load_dotenv()

# --- Environment Variables ---
MONGO_URI = os.getenv("MONGODB_URI")
HF_TOKEN = os.getenv('HF_TOKEN')
VECTOR_INDEX_NAME = os.getenv("VECTOR_INDEX_NAME", "vector_index") 

# --- Constants ---
DB_NAME = "news_database"
COLLECTION_NAME = "temp"
MAX_RESULTS_LIMIT = 5000 
# UPDATED: Increased the search limit to 500
VECTOR_SEARCH_LIMIT = 500
# NEW: Set the number of candidates for the search index to query
VECTOR_SEARCH_CANDIDATES = 2000 # Should be higher than the limit

# --- Hugging Face Login ---
if HF_TOKEN:
    print("Attempting to log in to Hugging Face...")
    login(token=HF_TOKEN)
    print("Hugging Face login successful or token already present.")

# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app)

# --- Embedding Model Initialization ---
embedding_model = None
try:
    print("Loading Sentence Transformer model...")
    embedding_model = SentenceTransformer('all-mpnet-base-v2')
    print("✅ Sentence Transformer model loaded successfully.")
except Exception as e:
    print(f"❌ Failed to load Sentence Transformer model: {e}")

# --- MongoDB Connection ---
client = None
if not MONGO_URI:
    print("❌ MONGO_URI environment variable not set.")
else:
    try:
        client = MongoClient(MONGO_URI)
        client.admin.command('ping')
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        print(f"✅ Successfully connected to MongoDB Atlas. Using DB: '{DB_NAME}', Collection: '{COLLECTION_NAME}'.")
    except (pymongo_errors.ConfigurationError, pymongo_errors.ConnectionFailure) as e:
        print(f"❌ MongoDB Connection Error: {e}")
        client = None

# --- Helper Function for Embeddings ---
def get_embeddings(text):
    if not embedding_model:
        print("❌ Embedding model is not available.")
        return None
    try:
        embedding = embedding_model.encode(text)
        return embedding.tolist()
    except Exception as e:
        print(f"Error getting sentence transformer embedding: {e}")
        return None

# --- Common Projection for Frontend ---
FRONTEND_PROJECTION = {
    '_id': 1, 'title': 1, 'summary': 1, 'url': 1,
    'latitude': 1, 'longitude': 1, 'SQLDATE': 1, 'SOURCEURL': 1
}

# --- API Routes ---
@app.route("/api/news")
def get_news_filtered():
    # This function remains the same
    if collection is None:
        return jsonify({"error": "Database connection not established."}), 500
    # ... (rest of the function is unchanged)
    query_keyword = request.args.get('q', default=None, type=str)
    date_from = request.args.get('from', default=None, type=str)
    date_to = request.args.get('to', default=None, type=str)
    fetch_all = request.args.get('fetchAll', 'false').lower() == 'true'
    is_specific_filter = bool(query_keyword or date_from or date_to)
    fetch_all_unlimited = fetch_all and not is_specific_filter
    pipeline = []
    if query_keyword:
        pipeline.append({
            '$search': {'index': 'default', 'text': {'query': query_keyword, 'path': {'wildcard': '*'}}}
        })
    match_conditions = {'latitude': {'$ne': None}, 'longitude': {'$ne': None}}
    date_filter = {}
    if date_from: date_filter['$gte'] = date_from
    if date_to: date_filter['$lte'] = date_to
    if date_filter: match_conditions['SQLDATE'] = date_filter
    pipeline.append({'$match': match_conditions})
    projection = {**FRONTEND_PROJECTION}
    if query_keyword:
        projection['score'] = {'$meta': 'searchScore'}
    pipeline.append({'$project': projection})
    if query_keyword:
        pipeline.append({'$sort': {'score': -1}})
    limit_to_apply = None
    if not fetch_all_unlimited:
        limit_to_apply = MAX_RESULTS_LIMIT
        pipeline.append({'$limit': limit_to_apply})
    try:
        results = list(collection.aggregate(pipeline))
        count = len(results)
        return json.loads(json_util.dumps({
            "results": results, "count": count,
            "limit_applied": limit_to_apply if limit_to_apply and count >= limit_to_apply else None
        }))
    except pymongo_errors.OperationFailure as e:
        return jsonify({"error": f"Database operation failed: {e.details.get('errmsg', str(e))}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route("/api/vector_search")
def vector_search_news():
    if collection is None or embedding_model is None:
        return jsonify({"error": "Backend service not ready (DB or AI Model)."}), 503

    query = request.args.get('q', default=None, type=str)
    if not query:
        return jsonify({"error": "A 'q' parameter is required for vector search."}), 400
    
    print(f"\n--- New Vector Search ---")
    print(f"Received query: '{query}'")
    print(f"Using vector index name: '{VECTOR_INDEX_NAME}'")

    query_vector = get_embeddings(query)
    if not query_vector:
        return jsonify({"error": "Failed to generate query embedding."}), 500

    # UPDATED Pipeline with score filtering
    pipeline = [
        {
            '$vectorSearch': {
                'index': VECTOR_INDEX_NAME, 
                'path': 'summary_embedding', 
                'queryVector': query_vector, 
                'numCandidates': VECTOR_SEARCH_CANDIDATES, 
                'limit': VECTOR_SEARCH_LIMIT
            }
        },
        # Project the score into a field so we can filter on it
        {
            '$project': {
                **FRONTEND_PROJECTION,
                'score': {'$meta': 'vectorSearchScore'}
            }
        },
        # NEW: Add a $match stage to filter by the similarity score
        {
            '$match': {
                'score': {
                    '$gt': 0.7
                }
            }
        }
    ]
    
    print(f"Executing Vector Search pipeline with score > 0.6 and limit {VECTOR_SEARCH_LIMIT}...")
    try:
        results = list(collection.aggregate(pipeline))
        count = len(results)
        print(f"Found {count} results matching the criteria.")
        return json.loads(json_util.dumps({"results": results, "count": count, "limit_applied": None}))
    except pymongo_errors.OperationFailure as e:
        err_msg = e.details.get('errmsg', str(e))
        print(f"❌ Vector Search DB Error: {err_msg}")
        if "index not found" in err_msg.lower():
            err_msg = f"Vector Search index '{VECTOR_INDEX_NAME}' not found. Please check your .env file and Atlas configuration."
        return jsonify({"error": f"Database operation failed: {err_msg}"}), 500
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

# --- Main Execution ---
if __name__ == '__main__':
    if client is None or embedding_model is None:
        print("❌ Backend cannot start: MongoDB or Embedding Model failed to initialize.")
    else:
        app.run(host='0.0.0.0', port=5001, debug=False)