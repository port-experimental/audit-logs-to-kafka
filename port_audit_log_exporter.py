import requests
from kafka import KafkaProducer
import json
import os
from datetime import datetime, timedelta
import dateutil.parser
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Fetch logs from Port.io API
port_api_token = os.getenv('PORT_API_TOKEN')
port_api_url = os.getenv('PORT_API_URL', 'https://api.getport.io')
kafka_server = os.getenv('KAFKA_SERVER', 'localhost:9092')
kafka_topic = os.getenv('KAFKA_TOPIC', 'port-logs')

# Create headers for API requests
headers = {
    "Authorization": f"{port_api_token}",
    "Content-Type": "application/json"
}

def get_last_processed_time():
    try:
        with open('last_processed.txt', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def save_last_processed_time(timestamp):
    with open('last_processed.txt', 'w') as f:
        f.write(timestamp)

def add_one_second(timestamp_str):
    """Add one second to the timestamp string and format it correctly"""
    dt = dateutil.parser.parse(timestamp_str)
    dt += timedelta(seconds=1)
    
    # Format as "YYYY-MM-DDTHH:MM:SS.sssZ"
    # Use microseconds/1000 to get milliseconds, and ensure 3 digits with zfill
    milliseconds = str(int(dt.microsecond / 1000)).zfill(3)
    formatted = dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{milliseconds}Z"
    
    return formatted

# Get last processed timestamp
last_processed = get_last_processed_time()
if last_processed:
    resp = requests.get(f"{port_api_url}/v1/audit-log?limit=1000&from={last_processed}", headers=headers)
else:
    resp = requests.get(f"{port_api_url}/v1/audit-log?limit=1000", headers=headers)

logs = resp.json()

# Print first log for debugging
if logs.get('ok') and 'audits' in logs and logs['audits']:
    print("First log structure:", json.dumps(logs['audits'][0], indent=2))

# Send logs to Kafka
producer = KafkaProducer(
    bootstrap_servers=kafka_server,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Process the audits array
if logs.get('ok') and 'audits' in logs:
    new_logs = logs['audits']
    if new_logs:
        for log in new_logs:
            producer.send(kafka_topic, log)
        print(f"Sent {len(new_logs)} new logs to Kafka topic '{kafka_topic}'")
        # Save the timestamp of the most recent log + 1 second
        if 'trigger' in new_logs[0] and 'at' in new_logs[0]['trigger']:
            timestamp_plus_one = add_one_second(new_logs[0]['trigger']['at'])
            save_last_processed_time(timestamp_plus_one)
            print(f"Next fetch will start from: {timestamp_plus_one}")
        else:
            print("Warning: No trigger.at field found in logs")
    else:
        print("No new logs found")
else:
    print("No logs found or invalid response structure")

producer.flush()
