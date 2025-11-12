import requests
from kafka import KafkaProducer
import json
import os
import sys
import argparse
from datetime import datetime, timedelta, timezone
import dateutil.parser
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Fetch logs from Port.io API
port_api_token = os.getenv("PORT_API_TOKEN")
port_api_url = os.getenv("PORT_API_URL", "https://api.getport.io")
kafka_server = os.getenv("KAFKA_SERVER", "localhost:9092")
kafka_topic = os.getenv("KAFKA_TOPIC", "port-logs")

# Kafka SSL configuration
kafka_ssl_ca_cert = os.getenv("KAFKA_SSL_CA_CERT")
kafka_ssl_client_cert = os.getenv("KAFKA_SSL_CLIENT_CERT")
kafka_ssl_client_key = os.getenv("KAFKA_SSL_CLIENT_KEY")

# Optional configuration
audit_limit = os.getenv("AUDIT_LIMIT")
from_date_env = os.getenv("FROM_DATE")
to_date_env = os.getenv("TO_DATE")

# Create headers for API requests
headers = {"Authorization": f"{port_api_token}", "Content-Type": "application/json"}


def validate_ssl_certificates():
    """Validate that SSL certificate files exist if SSL is configured"""
    if kafka_ssl_ca_cert or kafka_ssl_client_cert or kafka_ssl_client_key:
        # If any SSL cert is specified, all must be specified
        if not all([kafka_ssl_ca_cert, kafka_ssl_client_cert, kafka_ssl_client_key]):
            print(
                "Error: All SSL certificate paths must be provided (CA, client cert, and client key)"
            )
            sys.exit(1)

        # Check if files exist
        for cert_path, cert_name in [
            (kafka_ssl_ca_cert, "CA certificate"),
            (kafka_ssl_client_cert, "Client certificate"),
            (kafka_ssl_client_key, "Client key"),
        ]:
            if not os.path.exists(cert_path):
                print(f"Error: {cert_name} not found at: {cert_path}")
                sys.exit(1)
        return True
    return False


def validate_iso8601_date(date_string):
    """Validate and parse ISO 8601 date string"""
    try:
        dt = dateutil.parser.isoparse(date_string)
        # Ensure timezone awareness
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError) as e:
        print(f"Error: Invalid date format '{date_string}'. Expected ISO 8601 format (e.g., 2025-01-01T00:00:00.000Z)")
        sys.exit(1)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Export Port.io audit logs to Kafka"
    )
    parser.add_argument(
        "-f",
        "--from-date",
        help="Start date in ISO 8601 format (e.g., 2025-01-01T00:00:00.000Z)",
    )
    parser.add_argument(
        "-t",
        "--to-date",
        help="End date in ISO 8601 format (e.g., 2025-01-31T23:59:59.999Z)",
    )
    return parser.parse_args()


def get_last_processed_time():
    try:
        with open("last_processed.txt", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def save_last_processed_time(timestamp):
    with open("last_processed.txt", "w") as f:
        f.write(timestamp)


def add_one_second(timestamp_str):
    """Add one second to the timestamp string and format it correctly with timezone"""
    dt = dateutil.parser.parse(timestamp_str)
    
    # Ensure timezone awareness (default to UTC if not specified)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    dt += timedelta(seconds=1)

    # Convert to UTC for consistent storage
    dt_utc = dt.astimezone(timezone.utc)
    
    # Format as "YYYY-MM-DDTHH:MM:SS.sssZ"
    # Use microseconds/1000 to get milliseconds, and ensure 3 digits with zfill
    milliseconds = str(int(dt_utc.microsecond / 1000)).zfill(3)
    formatted = dt_utc.strftime("%Y-%m-%dT%H:%M:%S") + f".{milliseconds}Z"

    return formatted


def main():
    """Main execution function"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Validate required configuration
    if not port_api_token:
        print("Error: PORT_API_TOKEN environment variable is required")
        sys.exit(1)
    
    # Validate SSL certificates if configured
    use_ssl = validate_ssl_certificates()
    
    # Determine time range (CLI args > env vars > last_processed.txt)
    from_date = None
    to_date = None
    
    if args.from_date:
        # CLI argument takes precedence
        from_date = args.from_date
        print(f"Using from-date from CLI: {from_date}")
    elif from_date_env:
        # Environment variable as fallback
        from_date = from_date_env
        print(f"Using FROM_DATE from environment: {from_date}")
    else:
        # Use last processed time for backward compatibility
        last_processed = get_last_processed_time()
        if last_processed:
            from_date = last_processed
            print(f"Continuing from last processed time: {from_date}")
    
    if args.to_date:
        to_date = args.to_date
        print(f"Using to-date from CLI: {to_date}")
    elif to_date_env:
        to_date = to_date_env
        print(f"Using TO_DATE from environment: {to_date}")
    
    # Validate date formats if provided
    if from_date:
        validate_iso8601_date(from_date)
    if to_date:
        validate_iso8601_date(to_date)
    
    # Build API URL with parameters
    api_url = f"{port_api_url}/v1/audit-log"
    params = []
    
    if audit_limit:
        params.append(f"limit={audit_limit}")
        print(f"Using audit limit: {audit_limit}")
    
    if from_date:
        params.append(f"from={from_date}")
    
    if to_date:
        params.append(f"to={to_date}")
    
    if params:
        api_url += "?" + "&".join(params)
    
    print(f"Fetching audit logs from: {api_url}")
    
    # Fetch logs from Port.io API with error handling
    try:
        resp = requests.get(api_url, headers=headers, timeout=30)
        resp.raise_for_status()
        logs = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching audit logs: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing API response: {e}")
        sys.exit(1)
    
    # Print first log for debugging
    if logs.get("ok") and "audits" in logs and logs["audits"]:
        print("First log structure:", json.dumps(logs["audits"][0], indent=2))
    
    # Configure Kafka producer with SSL if enabled
    kafka_config = {
        "bootstrap_servers": kafka_server,
        "value_serializer": lambda v: json.dumps(v).encode("utf-8"),
    }
    
    if use_ssl:
        kafka_config.update({
            "security_protocol": "SSL",
            "ssl_cafile": kafka_ssl_ca_cert,
            "ssl_certfile": kafka_ssl_client_cert,
            "ssl_keyfile": kafka_ssl_client_key,
        })
        print("Kafka SSL encryption enabled")
    
    # Initialize Kafka producer with error handling
    try:
        producer = KafkaProducer(**kafka_config)
    except Exception as e:
        print(f"Error connecting to Kafka: {e}")
        sys.exit(1)
    
    # Process the audits array
    if logs.get("ok") and "audits" in logs:
        new_logs = logs["audits"]
        if new_logs:
            try:
                for log in new_logs:
                    producer.send(kafka_topic, log)
                producer.flush()
                print(f"Sent {len(new_logs)} new logs to Kafka topic '{kafka_topic}'")
                
                # Save the timestamp of the most recent log + 1 second
                # Only update last_processed if we're not using explicit date ranges
                if not args.from_date and not from_date_env:
                    if "trigger" in new_logs[0] and "at" in new_logs[0]["trigger"]:
                        timestamp_plus_one = add_one_second(new_logs[0]["trigger"]["at"])
                        save_last_processed_time(timestamp_plus_one)
                        print(f"Next fetch will start from: {timestamp_plus_one}")
                    else:
                        print("Warning: No trigger.at field found in logs")
            except Exception as e:
                print(f"Error sending logs to Kafka: {e}")
                sys.exit(1)
        else:
            print("No new logs found")
    else:
        error_msg = logs.get("message", "Unknown error")
        print(f"No logs found or invalid response structure: {error_msg}")
        sys.exit(1)
    
    producer.close()
    print("Audit log export completed successfully")


if __name__ == "__main__":
    main()
