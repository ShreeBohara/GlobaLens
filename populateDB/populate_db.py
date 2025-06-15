import pymongo
from faker import Faker
import random
import time


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


# --- Configuration ---
# IMPORTANT: Replace with your actual MongoDB connection string
DB_NAME = "news_database"
COLLECTION_NAME = "temp"
NUM_DOCUMENTS = 300000
BATCH_SIZE = 1000

# Initialize Faker for generating random data
fake = Faker()

def generate_random_article():
    """Generates a single fake news article document."""
    return {
        # --- THIS LINE IS THE FIX ---
        # Changed from fake.date_this_decade() to fake.date_time_this_decade()
        "SQLDATE": fake.date_time_this_decade(),
        
        "Numentions": random.randint(1, 100),
        "SOURCEURL": fake.url(),
        "Latitude": random.uniform(-90, 90),
        "Longitude": random.uniform(-180, 180),
        "Title": fake.sentence(nb_words=6),
        "text": fake.paragraph(nb_sentences=5),
        "summary": fake.paragraph(nb_sentences=2),
        "keywords": [fake.word() for _ in range(random.randint(5, 15))],
        "summary_embedding": [random.uniform(-1, 1) for _ in range(768)] # Example embedding
    }

def main():
    """Connects to MongoDB and populates the collection."""
    print("Connecting to MongoDB...")
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        # Optional: Drop the collection if it already exists to start fresh
        collection.drop()
        print(f"Collection '{COLLECTION_NAME}' dropped.")

        print(f"Generating and inserting {NUM_DOCUMENTS} documents in batches of {BATCH_SIZE}...")
        start_time = time.time()
        
        for i in range(0, NUM_DOCUMENTS, BATCH_SIZE):
            batch = [generate_random_article() for _ in range(BATCH_SIZE)]
            collection.insert_many(batch)
            print(f"Inserted batch {i//BATCH_SIZE + 1}/{(NUM_DOCUMENTS//BATCH_SIZE)}")

        end_time = time.time()
        print("\nData insertion complete!")
        print(f"Total documents inserted: {collection.count_documents({})}")
        print(f"Time taken: {end_time - start_time:.2f} seconds")

    except pymongo.errors.ConnectionFailure as e:
        print(f"Could not connect to MongoDB: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    main()