import asyncio, aiohttp, pandas as pd, os, json
from newspaper import Article
from concurrent.futures import ProcessPoolExecutor
from tqdm.asyncio import tqdm
import nltk
from google.cloud import storage
from dotenv import load_dotenv
import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import numpy as np
from sentence_transformers import SentenceTransformer
from huggingface_hub import login
from urllib.parse import quote
from google.cloud import storage

# Load environment variables from .env file for local testing
load_dotenv()

# --- NLTK Data Handling Configuration for Local Testing ---
try:
    nltk_data_path = os.path.join(os.path.expanduser("~"), "nltk_data")
    if not os.path.exists(os.path.join(nltk_data_path, 'tokenizers/punkt')):
        print("NLTK 'punkt' not found locally. Attempting download to user's home 'nltk_data' folder...")
        os.makedirs(nltk_data_path, exist_ok=True)
        nltk.download('punkt', download_dir=nltk_data_path, quiet=True)
        print("NLTK 'punkt' downloaded.")
    nltk.data.path.append(nltk_data_path)
except Exception as e:
    print(f"Warning: NLTK punkt setup failed locally: {e}")

# --- Global Configurations ---
CONN = 10
PROC = os.cpu_count() or 4
TIMEOUT = aiohttp.ClientTimeout(total=20)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36"}

_sentence_transformer_model = None # For SentenceTransformer model


# ---------- Helper functions for Article Extraction (Stage 2 Logic) ---------- #
def parse_article(html: str, url: str):
    """Parses HTML content using newspaper3k and returns extracted article details."""
    try:
        art = Article(url)
        art.set_html(html)
        art.parse()
        art.nlp()
        return {
            "title":    art.title,
            "text":     art.text,
            "summary":  art.summary,
            "keywords": art.keywords,
            "error":    None
        }
    except Exception as e:
        return {
            "title": None, "text": None, "summary": None,
            "keywords": None, "error": f"parse_error: {type(e).__name__}: {e}"
        }

async def fetch_html(session: aiohttp.ClientSession, url: str) -> tuple[str, str]:
    """Return (url, html) or (url, None) on error, with robust encoding."""
    try:
        async with session.get(url, timeout=TIMEOUT, headers=HEADERS) as r:
            r.raise_for_status()
            content_type_header = r.headers.get("Content-Type", "").lower()
            
            charset = None
            if 'charset=' in content_type_header:
                charset = content_type_header.split('charset=')[-1].split(';')[0].strip()
                
            raw_bytes = await r.read()

            decoded_text = None
            if charset:
                try:
                    decoded_text = raw_bytes.decode(charset)
                except (UnicodeDecodeError, LookupError):
                    print(f"Warning: Failed to decode {url} with declared charset '{charset}'. Trying fallbacks.")

            if decoded_text is None: # If no charset or decoding failed, try common fallbacks
                try:
                    decoded_text = raw_bytes.decode('utf-8', errors='strict')
                except UnicodeDecodeError:
                    try:
                        decoded_text = raw_bytes.decode('latin-1')
                        print(f"Decoded {url} with latin-1 due to UTF-8 error.")
                    except UnicodeDecodeError:
                        print(f"Critical decode failure for {url}. Giving up.")
                        return url, None
            
            if decoded_text and ("text/html" in content_type_header or "text/plain" in content_type_header):
                return url, decoded_text
            else:
                print(f"Skipping non-text content for {url}: {content_type_header}")
                return url, None
                
    except Exception as e:
        print(f"Failed to fetch {url}: {type(e).__name__}: {e}")
        return url, None

async def producer(urls, queue: asyncio.Queue):
    """Fetch pages concurrently and push html into a queue for parsing."""
    sem = asyncio.Semaphore(CONN)
    async with aiohttp.ClientSession() as sess:
        async def bounded_fetch(u):
            async with sem:
                return await fetch_html(sess, u)

        for coro in tqdm(asyncio.as_completed(map(bounded_fetch, urls)),
                         total=len(urls), desc="Downloading"):
            url, html = await coro
            await queue.put((url, html))
    for _ in range(PROC):
        await queue.put((None, None))

async def consumer(queue: asyncio.Queue, out_path: str):
    """Pop (url, html), run newspaper3k in a separate process, append to disk."""
    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor(max_workers=PROC) as pool:
        while True:
            url, html = await queue.get()
            if url is None:
                break

            if html is None:
                result = {"title": None, "text": None, "summary": None,
                          "keywords": None, "error": "download_failed"}
            else:
                try:
                    result = await loop.run_in_executor(pool, parse_article, html, url)
                except Exception as e:
                    result = {"title": None, "text": None, "summary": None,
                              "keywords": None, "error": f"parse_error: {e}"}

            with open(out_path, "a", encoding="utf8") as f:
                f.write(json.dumps({"url": url, **result}, ensure_ascii=False) + "\n")
            queue.task_done()

async def main_async_pipeline(urls, output_ndjson_path):
    """Main asynchronous orchestrator for fetching and parsing."""
    # NDJSON_OUT is no longer a global but passed as an argument.
    # The original GLOBAL_NDJSON_OUT_PATH was for Cloud Function version, can be removed if not needed.
    # For this local script, NDJSON_OUT is just a variable within this function's scope.
    
    queue = asyncio.Queue(maxsize=CONN * 2)
    consumers = [asyncio.create_task(consumer(queue, output_ndjson_path))
                 for _ in range(PROC)]
    await producer(urls, queue)
    await asyncio.gather(*consumers)


# ---------- Helper functions for Embedding Generation & MongoDB (Stage 3 Logic) ---------- #
def get_embeddings(text: str, embedding_type: str = "sentencetransformer", dimensionality: int = 768):
    """Generates embeddings for the given text using SentenceTransformer."""
    global _sentence_transformer_model

    if embedding_type == "sentencetransformer":
        if _sentence_transformer_model is None:
            print("Initializing SentenceTransformer model (all-mpnet-base-v2)... This may take a moment on first run.")
            try:
                hf_token = os.getenv('HF_TOKEN')
                if hf_token:
                    login(token=hf_token, add_to_git_credential=False)
                _sentence_transformer_model = SentenceTransformer('all-mpnet-base-v2')
                print("SentenceTransformer model loaded.")
            except Exception as e:
                print(f"Error loading SentenceTransformer model: {e}")
                return None
        
        try:
            if pd.isna(text) or text is None:
                return None
            embedding = _sentence_transformer_model.encode(text)
            return embedding.tolist()
        except Exception as e:
            print(f"Error generating embedding for text: '{str(text)[:50]}...': {e}")
            return None
    else:
        print(f"Unsupported embedding type: {embedding_type}")
        return None

def connect_to_mongodb():
    username = os.getenv("MONGODB_USERNAME")
    password = os.getenv("MONGODB_PASSWORD")
    host = os.getenv("MONGODB_HOST")

    if not username or not password or not host:
        raise ValueError("MONGODB_USERNAME, MONGODB_PASSWORD, MONGODB_HOST must be set in your .env file.")

    username_encoded = quote(username)
    password_encoded = quote(password)

    mongo_uri = f"mongodb+srv://{username_encoded}:{password_encoded}@{host}/?retryWrites=true&w=majority&appName=Cluster0"
    
    try:
        client = MongoClient(mongo_uri)
        client.admin.command('ping') 
        print("Successfully connected to MongoDB!")
        return client
    except ConnectionFailure as e:
        print(f"Could not connect to MongoDB: {e}")
        return None


# ------------------------------ Main Local Batch Processor Loop ------------------------------- #
if __name__ == "__main__":
    print("Starting GDELT Batch Processor: Pulling, Extracting, Embedding, and Uploading to MongoDB...")

    # --- Setup GCS Client ---
    storage_client = storage.Client() # Use one client
    
    source_bucket_name = os.getenv('GCS_BUCKET_NAME')
    backup_data_prefix = "backup_data/" # NEW: Prefix for backup folder within the same bucket
    
    if not source_bucket_name:
        raise ValueError("GCS_BUCKET_NAME must be set in your .env file.")
    
    source_bucket = storage_client.bucket(source_bucket_name)

    cleaned_data_prefix = "cleaned_data/"
    
    # --- Setup MongoDB Client (outside the loop for efficiency) ---
    mongo_client = connect_to_mongodb()
    if not mongo_client:
        print("Cannot proceed without MongoDB connection.")
        exit(1)

    db = mongo_client['news_database']
    collection = db['articles']

    # --- Define Local Temporary Directories ---
    local_temp_dir = "/tmp" # For downloaded CSVs
    local_extracted_articles_output_dir = "extracted_articles_local" # For NDJSON output from article extraction

    os.makedirs(local_extracted_articles_output_dir, exist_ok=True)


    # --- Main Processing Loop ---
    processed_files_count = 0
    while True:
        # 1. Find the Oldest Cleaned CSV in GCS
        oldest_blob = None
        oldest_timestamp = None
        print(f"\nSearching for oldest cleaned CSV in gs://{source_bucket_name}/{cleaned_data_prefix}...")

        blobs_iterator = storage_client.list_blobs(source_bucket_name, prefix=cleaned_data_prefix)
        
        for blob in blobs_iterator:
            if blob.name.endswith("_cleaned.csv") and blob.name.startswith(cleaned_data_prefix):
                filename_without_prefix = blob.name.replace(cleaned_data_prefix, "")
                timestamp_str = filename_without_prefix.split('_cleaned.csv')[0]
                try:
                    current_blob_timestamp = datetime.datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
                    if oldest_timestamp is None or current_blob_timestamp < oldest_timestamp:
                        oldest_timestamp = current_blob_timestamp
                        oldest_blob = blob
                except ValueError:
                    print(f"Warning: Could not parse timestamp from filename: {blob.name}. Skipping this file.")
                    continue

        if oldest_blob is None:
            print("No more cleaned CSV files found in GCS bucket. All available files processed or none existed.")
            break # Exit loop if no more files

        print(f"Found oldest CSV to process: {oldest_blob.name}")
        gcs_csv_path_to_process = f"gs://{source_bucket_name}/{oldest_blob.name}"
        
        # 2. Download the oldest Cleaned CSV locally to /tmp
        local_csv_path_to_process = os.path.join(local_temp_dir, os.path.basename(oldest_blob.name))
        
        try:
            print(f"Downloading {gcs_csv_path_to_process} to {local_csv_path_to_process}")
            oldest_blob.download_to_filename(local_csv_path_to_process)
            print(f"Downloaded oldest CSV to: {local_csv_path_to_process}")

            # 3. Read CSV to get SOURCEURLs and perform Article Extraction
            df_cleaned_csv = pd.read_csv(local_csv_path_to_process)
            urls_to_fetch = df_cleaned_csv["SOURCEURL"].dropna().unique().tolist()
            print(f"Found {len(urls_to_fetch):,} unique URLs from CSV: {local_csv_path_to_process}")

            # Define local output NDJSON path for this batch
            timestamp_for_output = os.path.basename(local_csv_path_to_process).replace('_cleaned.csv', '')
            local_ndjson_output_path = os.path.join(local_extracted_articles_output_dir, f"{timestamp_for_output}_articles.ndjson")
            
            if not urls_to_fetch:
                print("No URLs found in this CSV. Skipping article extraction.")
                extracted_articles_data = [] # Empty list if no URLs to fetch
            else:
                print("Starting asynchronous article fetching and parsing for this batch...")
                if os.path.exists(local_ndjson_output_path):
                    os.remove(local_ndjson_output_path)
                
                asyncio.run(main_async_pipeline(urls_to_fetch, local_ndjson_output_path))
                print("Asynchronous article fetching and parsing complete.")

                extracted_articles_data = []
                if os.path.exists(local_ndjson_output_path):
                    with open(local_ndjson_output_path, 'r', encoding='utf8') as f:
                        for line in f:
                            try:
                                extracted_articles_data.append(json.loads(line))
                            except json.JSONDecodeError as jde:
                                print(f"Warning: JSON decode error in {local_ndjson_output_path} line: {jde}")
                print(f"Loaded {len(extracted_articles_data)} extracted articles from {local_ndjson_output_path}.")
            
            # 4. Combine data, Generate Embeddings, and Upload to MongoDB
            ndjson_lookup = {art.get('url'): art for art in extracted_articles_data}
            records_to_insert = []
            
            for index, row in df_cleaned_csv.iterrows():
                csv_row_data = {
                    'SQLDATE': row['SQLDATE'].strftime('%Y-%m-%d') if pd.notnull(row['SQLDATE']) and isinstance(row['SQLDATE'], pd.Timestamp) else row['SQLDATE'],
                    'NumMentions': row['NumMentions'],
                    'SOURCEURL': row['SOURCEURL'],
                    'latitude': row['latitude'],
                    'longitude': row['longitude']
                }
                url = row['SOURCEURL']

                combined_article = csv_row_data.copy()
                if url in ndjson_lookup:
                    ndjson_article = ndjson_lookup[url]
                    combined_article.update({k: v for k, v in ndjson_article.items() if k != 'error'})
                    
                    summary_text = combined_article.get('summary')
                    if summary_text and isinstance(summary_text, str) and summary_text.strip() and summary_text != 'null':
                        summary_embedding = get_embeddings(summary_text, embedding_type="sentencetransformer")
                        if summary_embedding:
                            combined_article['summary_embedding'] = summary_embedding
                        else:
                            print(f"Warning: Failed to generate embedding for summary of URL: {url}")
                            combined_article['embedding_error'] = 'embedding_generation_failed'
                    else:
                        combined_article['summary_embedding'] = None
                else:
                    print(f"Warning: URL {url} not found in extracted NDJSON data, adding CSV data only with error flag.")
                    combined_article.update({
                        'title': None, 'text': None, 'summary': None, 'keywords': None,
                        'error': 'no_ndjson_match'
                    })
                records_to_insert.append(combined_article)
            
            print(f"Prepared {len(records_to_insert)} records for MongoDB insertion for this batch.")

            if records_to_insert:
                collection.insert_many(records_to_insert)
                print(f"Successfully inserted {len(records_to_insert)} articles for batch '{timestamp_for_output}' into MongoDB.")
            else:
                print(f"No records to insert into MongoDB for batch '{timestamp_for_output}'.")

            # 5. Move the processed _cleaned.csv file to backup folder or delete
            # Destination path in backup folder
            destination_blob_name = f"{backup_data_prefix}{oldest_blob.name.replace(cleaned_data_prefix, '')}" # NEW: Destination blob name

            try:
                # Correct way to copy the blob to the backup folder
                source_bucket.copy_blob(oldest_blob, source_bucket, destination_blob_name)
                print(f"Copied {oldest_blob.name} to gs://{source_bucket_name}/{destination_blob_name}")

                # Delete the original blob from the source folder
                oldest_blob.delete()
                print(f"Deleted original processed CSV from GCS: {oldest_blob.name}")
            except Exception as e:
                print(f"ERROR: Failed to move {oldest_blob.name} to backup folder: {e}")
                # If move fails, original is left in source for manual inspection
            
            processed_files_count += 1

        except Exception as e:
            print(f"ERROR: Failed to process batch '{gcs_csv_path_to_process}': {e}")
            import traceback
            traceback.print_exc()
            print(f"Skipping to next file due to error in processing: {gcs_csv_path_to_process}")
        finally:
            # Clean up local temporary files for this batch
            if os.path.exists(local_csv_path_to_process):
                os.remove(local_csv_path_to_process)
                print(f"Cleaned up local temp CSV: {local_csv_path_to_process}")
            if os.path.exists(local_ndjson_output_path):
                os.remove(local_ndjson_output_path)
                print(f"Cleaned up local temp NDJSON: {local_ndjson_output_path}")
    
    print(f"\nBatch processing complete! Total files processed: {processed_files_count}")
    mongo_client.close()
    print("MongoDB connection closed.")


