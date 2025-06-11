import json
import pandas as pd
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import numpy as np
# from vertexai.preview.generative_models import GenerativeModel
import vertexai
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import google.auth
from huggingface_hub import login

# Load environment variables
load_dotenv()

# Hugging Face token
HF_TOKEN = os.getenv('HF_TOKEN')
if HF_TOKEN:
    login(token=HF_TOKEN)

PROJECT_ID = "thermal-setup-442101-b6"
REGION = "us-central1"

# creds, _ = google.auth.default(quota_project_id=PROJECT_ID)

vertexai.init(project=PROJECT_ID, location=REGION)#, credentials=creds)

# MongoDB connection string
MONGODB_URI = os.getenv('MONGODB_URI')

def get_embeddings(text, embeddding_type = "sentencetransformer", dimensionality = 256, task = "RETRIEVAL_DOCUMENT"):
    """Get embeddings using Vertex AI's text embedding model."""

    if embeddding_type == "sentencetransformer":
        try:
            model = SentenceTransformer('all-mpnet-base-v2', use_auth_token=HF_TOKEN)
            embedding = model.encode(text)
            return embedding.tolist()
        except Exception as e:
            print(f"Error getting sentence transformer embedding: {e}")
            return None
    else:
        try:
            # model = GenerativeModel("textembedding-gecko@001")
            model = TextEmbeddingModel.from_pretrained("text-embedding-005")
            inputs = TextEmbeddingInput(text, task)
            kwargs = dict(output_dimensionality=dimensionality) if dimensionality else {}
            embedding_response = model.get_embeddings(inputs, **kwargs)
            if embedding_response and len(embedding_response) > 0:
                return embedding_response[0].values
            print(f"Warning: Vertex AI returned no embeddings for text: {text[:100]}...")
            return None
        except Exception as e:
            print(f"Error getting vertex AI embedding: {e}")
            return None

def connect_to_mongodb():
    try:
        client = MongoClient(MONGODB_URI)
        # Verify connection
        client.admin.command('ping')
        print("Successfully connected to MongoDB!")
        return client
    except ConnectionFailure as e:
        print(f"Could not connect to MongoDB: {e}")
        return None

def load_articles_to_mongodb(client, limit=1000):
    db = client['news_database']
    collection = db['articles']
    
    # Load articles from ndjson file
    articles = []
    print(f"Starting to load up to {limit} articles...")
    with open('articles.ndjson', 'r', encoding='utf-8') as file:
        for i, line in enumerate(file):
            if i >= limit:
                print(f"Reached limit of {limit} articles.")
                break
            print(f"Processing article {i+1}/{limit}...")
            article = json.loads(line)
            
            # Generate embeddings for summary and keywords
            if article.get('summary'):
                summary_embedding = get_embeddings(article['summary'])
                if summary_embedding:
                    article['summary_embedding'] = summary_embedding
            
            if article.get('keywords'):
                # Convert keywords list to string for embedding
                keywords_text = ' '.join(article['keywords'])
                keywords_embedding = get_embeddings(keywords_text)
                if keywords_embedding:
                    article['keywords_embedding'] = keywords_embedding
            
            articles.append(article)
    
    # Insert articles into MongoDB
    if articles:
        collection.insert_many(articles)
        print(f"Successfully inserted {len(articles)} articles into MongoDB")
    else:
        print("No articles to insert")

# Don't use this function, it's not working
def create_vector_search_index(client):
    db = client['news_database']
    collection = db['articles']
    
    # Create vector search index for summary and keywords embeddings
    index_definition = {
        "mappings": {
            "dynamic": False,
            "fields": {
                "summary_embedding": {
                    "type": "knnVector",
                    "dimensions": 768,
                    "similarity": "cosine"
                }#,
                # "keywords_embedding": {
                #     "type": "knnVector",
                #     "dimensions": 768,
                #     "similarity": "cosine"
                # }
            }
        }
    }
    
    try:
        # Create the search index using the Atlas Search API
        db.command({
            "createSearchIndexes": collection.name,
            "indexes": [{
                "name": "vector_search_index",
                "definition": index_definition
            }]
        })
        print("Successfully created vector search index")
    except Exception as e:
        print(f"Error creating index: {e}")
        # If index already exists, try to update it
        try:
            db.command({
                "updateSearchIndex": collection.name,
                "name": "vector_search_index",
                "definition": index_definition
            })
            print("Successfully updated existing vector search index")
        except Exception as update_error:
            print(f"Error updating index: {update_error}")
            raise update_error

def search_articles(client, query, similarity_threshold=0.1):
    db = client['news_database']
    collection = db['articles']
    
    # Generate query vector using Vertex AI
    query_vector = get_embeddings(query)
    if not query_vector:
        print("Failed to generate query embedding")
        return
    
    # Perform vector search
    search_query = [
                {
                    '$vectorSearch': {
                    'index': 'new_vector', 
                        'path': 'summary_embedding', 
                        'queryVector': query_vector, 
                    'numCandidates': 200, 
                    'limit': 10
                    }
                }, {
                    '$project': {
                    '_id': 0, 
                    'title': 1, 
                    'summary': 1, 
                    'keywords': 1, 
                    'score': {
                        '$meta': 'vectorSearchScore'
                    }
                    }
                }
                ]
    
    # Execute search
    try:
        results = list(collection.aggregate(search_query))
        
        # Filter results by similarity score after retrieval
        # filtered_results = [r for r in results if r.get('score', 0) >= similarity_threshold]
        
        for i, result in enumerate(results, 1):
            print(f"\n{i}. Title: {result.get('title', 'N/A')}")
            print(f"   Summary: {result.get('summary', 'N/A')}")
            print(f"   Keywords: {result.get('keywords', 'N/A')}")
            print(f"   Similarity Score: {result.get('score', 'N/A')}")
    except Exception as e:
        print(f"Error performing search: {e}")
        raise e

def main():
    # Connect to MongoDB
    client = connect_to_mongodb()
    if not client:
        return
    
    # Load articles
    # load_articles_to_mongodb(client)
    
    # Create vector search index
    # create_vector_search_index(client)
    
    # Interactive search
    while True:
        query = input("\nEnter your search query (or 'quit' to exit): ")
        if query.lower() == 'quit':
            break
        
        search_articles(client, query)
    
    client.close()

if __name__ == "__main__":
    main() 