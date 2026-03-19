import json
import time
import random
import os
from datetime import datetime
from google.cloud import pubsub_v1

# CONFIGURATION
PROJECT_ID = os.environ.get("PROJECT_ID")

if not PROJECT_ID:
    print("ERROR: Please set the PROJECT_ID environment variable.")
    print("PowerShell Example: $env:PROJECT_ID='your-project-id'")
    exit(1)

TOPIC_ID = "website-logs"

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

FEEDBACK_SAMPLES = [
    "I love the new interface!", "The checkout is confusing.",
    "Great selection.", "Website is too slow.",
    "Amazing experience!", "I cannot find the search button."
]

def run_simulator():
    print(f"Publishing to {topic_path}...")
    try:
        while True:
            # 30% chance of leaving feedback
            comment = random.choice(FEEDBACK_SAMPLES) if random.random() < 0.3 else None
            
            data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "user_id": f"USER_{random.randint(1,50):03d}",
                "action": random.choice(["view", "click", "add_to_cart", "purchase"]),
                "page": random.choice(["/home", "/cart", "/product"]),
                "response_time_ms": random.randint(50, 800),
                "feedback": comment
            }
            
            future = publisher.publish(topic_path, json.dumps(data).encode("utf-8"))
            print(f"Sent: {data['user_id']}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopped.")

if __name__ == "__main__":
    run_simulator()
