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
COLLECTION_NAME = "articles" # UPDATED: Use the 'articles' collection
# Default limit for specific searches, not for initial full load
MAX_RESULTS_LIMIT_FOR_SPECIFIC_SEARCH = 5000 

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
    except pymongo_errors.ConnectionFailure as cfe: 
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
    - Queries the 'articles' collection.
    """
    if collection is None or client is None:
        return jsonify({"error": "Database connection not established. Check backend logs."}), 500

    query_keyword = request.args.get('q', default=None, type=str)
    date_from = request.args.get('from', default=None, type=str)
    date_to = request.args.get('to', default=None, type=str)
    fetch_all_param = request.args.get('fetchAll', default='false', type=str).lower() == 'true'

    is_specific_filter_active = bool(query_keyword or date_from or date_to)

    fetch_all_unlimited_requested = fetch_all_param and not is_specific_filter_active

    pipeline = []
    limit_to_apply = None 

    # --- Stage 1: Atlas Search (if a keyword is provided) ---
    if query_keyword:
        pipeline.append({
            '$search': {
                # IMPORTANT: Ensure 'default' is the correct Atlas Search index name for your 'articles' collection.
                # This index should be configured to search fields like 'title', 'summary', 'text', 'keywords' etc.
                'index': 'default', 
                'text': {
                    'query': query_keyword,
                    'path': {'wildcard': '*'}, # Searches all indexed text fields
                    'fuzzy': {} 
                }
            }
        })

    # --- Stage 2: Filter by date and location (using $match) ---
    # Ensure 'latitude' and 'longitude' fields exist and are queryable in the 'articles' collection.
    match_conditions = {
        'latitude': {'$ne': None, '$exists': True},
        'longitude': {'$ne': None, '$exists': True}
    }
    date_filter_conditions = {}
    if date_from:
        # Assuming SQLDATE is stored as YYYY-MM-DD string or a format comparable with strings.
        # For BSON dates, you'd convert date_from/date_to to datetime objects.
        date_filter_conditions['$gte'] = date_from
    if date_to:
        date_filter_conditions['$lte'] = date_to

    if date_filter_conditions:
        match_conditions['SQLDATE'] = date_filter_conditions # SQLDATE is used for timestamp

    pipeline.append({'$match': match_conditions})

    # --- Stage 3: Project only the fields we need ---
    # Adjust fields based on the 'articles' collection structure and frontend needs
    projection_fields = {
        '_id': 1,
        'title': 1,       # From 'articles' collection
        'summary': '$summary', # Assuming 'text' field from articles is the main summary
                            # Or use '$summary' if that's the preferred summary field
        'url': 1,         # From 'articles' collection
        'latitude': 1,    # From 'articles' collection
        'longitude': 1,   # From 'articles' collection
        'SQLDATE': 1,     # Timestamp field
        # Add any other fields from 'articles' that are needed by the frontend.
        # e.g., 'keywords': 1, 'SOURCEURL': 1 (if different from 'url' and needed)
        # 'avgTone' is removed as it's assumed not to be in 'articles'.
        # 'GLOBALEVENTID' is removed, _id will be used.
    }
    if query_keyword:
        projection_fields['score'] = {'$meta': 'searchScore'}
    
    pipeline.append({'$project': projection_fields})

    # --- Optional Stage: Sort by relevance score if keyword search was done ---
    if query_keyword:
        pipeline.append({'$sort': {'score': -1}})

    # --- Stage 4: Limit the number of results ---
    if not fetch_all_unlimited_requested:
        limit_to_apply = MAX_RESULTS_LIMIT_FOR_SPECIFIC_SEARCH
        pipeline.append({'$limit': limit_to_apply})
        print(f"Applying limit of {limit_to_apply}. fetch_all_unlimited_requested: {fetch_all_unlimited_requested}, is_specific_filter_active: {is_specific_filter_active}")
    else:
        print(f"Fetching results without limit. fetch_all_unlimited_requested: {fetch_all_unlimited_requested}")

    try:
        print(f"Executing MongoDB Aggregation Pipeline on '{COLLECTION_NAME}': {json.dumps(pipeline, indent=2)}")
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
        # Try to provide a more specific error message if available
        error_message = ofe.details.get('errmsg', str(ofe)) if ofe.details else str(ofe)
        if "index not found" in error_message.lower():
             error_message += f". Please ensure an Atlas Search index named 'default' (or as configured) exists for the '{DB_NAME}.{COLLECTION_NAME}' collection and is properly configured."
        return jsonify({"error": f"Database operation failed: {error_message}"}), 500
    except Exception as e:
        print(f"❌ An unexpected error occurred during data fetching: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

# --- Main Execution ---
if __name__ == '__main__':
    if client is None:
        print("Backend cannot start: MongoDB connection was not established. Please check your MONGO_URI and network settings.")
    else:
        app.run(host='0.0.0.0', port=5001, debug=True)