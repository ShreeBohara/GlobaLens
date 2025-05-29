from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient, errors as pymongo_errors # Import specific errors
from bson import json_util
import json
import os
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv() # Load variables from the .env file

MONGO_URI = os.getenv("MONGODB_URI")
DB_NAME = "news_database" # Your database name
COLLECTION_NAME = "filtered_data" # Your collection name
# Default limit for specific searches, not for initial full load
MAX_RESULTS_LIMIT_FOR_SPECIFIC_SEARCH = 5000 # Updated limit

# --- Flask App Initialization ---
app = Flask(__name__)
# Enable CORS to allow your React app to make requests to this backend
CORS(app)

# --- MongoDB Connection ---
client = None
db = None
collection = None

if not MONGO_URI:
    print("❌ MONGO_URI environment variable not set. Please create a .env file with your Atlas connection string.")
else:
    try:
        client = MongoClient(MONGO_URI)
        # Ping the server to verify connection
        client.admin.command('ping')
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        print(f"✅ Successfully connected to MongoDB Atlas. Database: '{DB_NAME}', Collection: '{COLLECTION_NAME}'.")
    except pymongo_errors.ConfigurationError as ce:
        print(f"❌ MongoDB Configuration Error: {ce}. Check your MONGO_URI.")
    except pymongo_errors.ConnectionFailure as cfe: # Corrected variable name for ConnectionFailure
        print(f"❌ MongoDB Connection Failure: {cfe}. Check network/firewall and Atlas IP Whitelist.")
    except Exception as e:
        print(f"❌ An unexpected error occurred connecting to MongoDB Atlas: {e}")
        client = None # Ensure client is None if connection fails

# --- API Routes ---

@app.route("/api/news")
def get_news_filtered():
    """
    API endpoint that supports:
    - Fetching all data if fetchAll=true is passed and no other specific filters.
    - Filtering by keyword (using Atlas Search), start date, and end date.
    - Applying a limit for specific filtered searches or if no parameters (and no fetchAll=true) are provided.
    """
    if collection is None or client is None:
        return jsonify({"error": "Database connection not established. Check backend logs."}), 500

    query_keyword = request.args.get('q', default=None, type=str)
    date_from = request.args.get('from', default=None, type=str)
    date_to = request.args.get('to', default=None, type=str)
    fetch_all_param = request.args.get('fetchAll', default='false', type=str).lower() == 'true'

    is_specific_filter_active = bool(query_keyword or date_from or date_to)

    # Determine if we should fetch all data without a limit.
    # This is true ONLY if fetchAll=true is explicitly passed 
    # AND no other specific search/date filters are active.
    fetch_all_unlimited_requested = fetch_all_param and not is_specific_filter_active

    pipeline = []
    limit_to_apply = None 

    # --- Stage 1: Atlas Search (if a keyword is provided) ---
    if query_keyword:
        pipeline.append({
            '$search': {
                'index': 'default', # IMPORTANT: Replace 'default' with your Atlas Search index name
                'text': {
                    'query': query_keyword,
                    'path': {'wildcard': '*'}, 
                    'fuzzy': {} 
                }
            }
        })

    # --- Stage 2: Filter by date and location (using $match) ---
    match_conditions = {
        'ActionGeo_Lat': {'$ne': None, '$exists': True},
        'ActionGeo_Long': {'$ne': None, '$exists': True}
    }
    date_filter_conditions = {}
    if date_from:
        date_filter_conditions['$gte'] = date_from
    if date_to:
        date_filter_conditions['$lte'] = date_to

    if date_filter_conditions:
        match_conditions['SQLDATE'] = date_filter_conditions

    pipeline.append({'$match': match_conditions})

    # --- Stage 3: Project only the fields we need ---
    projection_stage = {
        '$project': {
            '_id': 1, 'GLOBALEVENTID': 1, 'SOURCEURL': 1, 'Actor1Name': 1,
            'Actor2Name': 1, 'GoldsteinScale': 1, 'SQLDATE': 1, 'AvgTone': 1,
            'ActionGeo_Lat': 1, 'ActionGeo_Long': 1,
        }
    }
    if query_keyword:
        projection_stage['$project']['score'] = {'$meta': 'searchScore'}
    pipeline.append(projection_stage)

    # --- Optional Stage: Sort by relevance score if keyword search was done ---
    if query_keyword:
        pipeline.append({'$sort': {'score': -1}})

    # --- Stage 4: Limit the number of results ---
    if not fetch_all_unlimited_requested:
        # Apply limit if it's NOT an explicit "fetch all unlimited" request.
        # This means it's either a specific query (keyword/date) 
        # OR an implicit query with no parameters and fetchAll=false (e.g. /api/news called without params).
        limit_to_apply = MAX_RESULTS_LIMIT_FOR_SPECIFIC_SEARCH
        pipeline.append({'$limit': limit_to_apply})
        print(f"Applying limit of {limit_to_apply}. fetch_all_unlimited_requested: {fetch_all_unlimited_requested}, is_specific_filter_active: {is_specific_filter_active}")
    else:
        print(f"Fetching results without limit. fetch_all_unlimited_requested: {fetch_all_unlimited_requested}")

    try:
        print(f"Executing MongoDB Aggregation Pipeline: {json.dumps(pipeline, indent=2)}")
        news_data = list(collection.aggregate(pipeline))
        results_count = len(news_data)
        print(f"MongoDB query returned {results_count} documents.")

        return json.loads(json_util.dumps({
            "results": news_data,
            "count": results_count,
            "limit_applied": limit_to_apply if limit_to_apply and results_count >= limit_to_apply else None
        }))

    except pymongo_errors.OperationFailure as ofe:
        print(f"❌ MongoDB Operation Failure (e.g., Atlas Search issue): {ofe}")
        print(f"Details: {ofe.details}")
        return jsonify({"error": f"Database operation failed: {ofe.details.get('errmsg', str(ofe))}"}), 500
    except Exception as e:
        print(f"❌ An unexpected error occurred during data fetching: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

# --- Main Execution ---
if __name__ == '__main__':
    if client is None:
        print("Backend cannot start: MongoDB connection was not established. Please check your MONGO_URI and network settings.")
    else:
        app.run(host='0.0.0.0', port=5001, debug=True)
