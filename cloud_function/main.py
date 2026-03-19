import base64
import json
import os
from google.cloud import language_v1
from google.cloud import bigquery
import functions_framework

# Initialize clients once globally to reuse the connection pool across function invocations
bq_client = bigquery.Client()
nl_client = language_v1.LanguageServiceClient()

# Project ID is automatically provided in Cloud Functions Gen2 or we fallback to GCP env vars
PROJECT_ID = os.environ.get('GCP_PROJECT', os.environ.get('GCLOUD_PROJECT'))
DATASET_ID = "analytics_ds"
TABLE_ID = "website_logs"

@functions_framework.cloud_event
def process_logs(cloud_event):
    """Triggered from a message on the Pub/Sub topic."""
    
    # 1. Receive and Decode Pub/Sub Message
    pubsub_message = cloud_event.data["message"]
    if "data" not in pubsub_message:
        print("No data found in Pub/Sub message.")
        return
        
    try:
        # Decode base64 payload
        decoded_data = base64.b64decode(pubsub_message["data"]).decode("utf-8")
        
        # 2. Parse JSON
        log_entry = json.loads(decoded_data)
        print(f"Processing log for user: {log_entry.get('user_id')} doing {log_entry.get('action')}")
        
    except Exception as parse_err:
        print(f"Failed to parse Pub/Sub data. Error: {parse_err}")
        return

    # 3. Call Natural Language API for sentiment_score
    # ML Requirement: detect if the log contains feedback. If yes, call the NLP API.
    feedback = log_entry.get("feedback")
    sentiment_score = None  # NULL if no feedback present
    
    if feedback and feedback.strip() != "":
        try:
            document = language_v1.Document(
                content=feedback, 
                type_=language_v1.Document.Type.PLAIN_TEXT
            )
            # Analyze sentiment remotely using Google NLP
            sentiment = nl_client.analyze_sentiment(
                request={"document": document}
            ).document_sentiment
            
            sentiment_score = sentiment.score
            print(f"Sentiment Score: {sentiment_score:.2f} for feedback: '{feedback[:40]}...'")
        except Exception as nlp_err:
            print(f"NLP API analyzing error. Proceeding with None. Error: {nlp_err}")
            sentiment_score = None
    else:
        print("No feedback in this log entry, skipping NLP analysis.")

    # 4. Build BigQuery row matching the required schema
    bq_row = {
        "user_id": str(log_entry.get("user_id")),
        "action": str(log_entry.get("action")),
        "timestamp": str(log_entry.get("timestamp")),
        "page": str(log_entry.get("page", "")),
        "response_time_ms": int(log_entry.get("response_time_ms", 0)),
        "feedback": str(feedback) if feedback else None,
        "sentiment_score": float(sentiment_score) if sentiment_score is not None else None
    }
    
    # 5. Save to BigQuery Table
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}" if PROJECT_ID else f"{bq_client.project}.{DATASET_ID}.{TABLE_ID}"
    
    try:
        # Stream data into BigQuery dataset
        errors = bq_client.insert_rows_json(table_ref, [bq_row])
        if errors:
            print(f"Found errors while streaming inserts: {errors}")
            raise Exception("Failed BigQuery insert_rows_json")
        else:
            print(f"Successfully inserted log entry into BigQuery table {table_ref}")
    except Exception as bq_err:
        print(f"An error occurred pushing to BigQuery: {bq_err}")
