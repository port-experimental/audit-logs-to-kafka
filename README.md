![port-oss-category](https://github.com/port-experimental/oss-images/blob/main/example-code.png)

# Port Audit Log Exporter

This script exports audit logs from Port to a Kafka stream for SIEM ingestion. It tracks the last processed log to ensure only new logs are exported.

## Prerequisites

- Python 3.7+
- Kafka cluster
- Port.io API access and token

## Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your configuration:
   ```bash
   cp .env.example .env
   ```
   Then edit the `.env` file with your specific values.

## Configuration

Create a `.env` file with the following variables:

### Required Variables

```bash
# Port API Configuration
PORT_API_TOKEN=Bearer your_token_here
PORT_API_URL=https://api.getport.io
KAFKA_SERVER=localhost:9092
KAFKA_TOPIC=port-logs
```

- `PORT_API_TOKEN`: Your Port.io API token with "Bearer " prefix (required)
- `PORT_API_URL`: The Port.io API endpoint (default: https://api.getport.io)
- `KAFKA_SERVER`: Kafka broker address (default: localhost:9092)
- `KAFKA_TOPIC`: Kafka topic to send logs to (default: port-logs)

### Kafka SSL Configuration (Optional)

For secure Kafka connections using SSL client certificates:

```bash
# Kafka SSL Certificate Authentication
KAFKA_SSL_CA_CERT=/path/to/ca-cert.pem
KAFKA_SSL_CLIENT_CERT=/path/to/client-cert.pem
KAFKA_SSL_CLIENT_KEY=/path/to/client-key.pem
```

**Note**: All three SSL certificate paths must be provided together. If any one is specified, all three are required.

### Optional Time Range Configuration

```bash
# Define a specific time range for audit log retrieval
FROM_DATE=2025-01-01T00:00:00.000Z
TO_DATE=2025-01-31T23:59:59.999Z
```

- `FROM_DATE`: Starting timestamp in ISO 8601 format
- `TO_DATE`: Ending timestamp in ISO 8601 format (optional)

### Optional Limit Configuration

```bash
# Set a custom limit for audit logs per request
AUDIT_LIMIT=5000
```

- `AUDIT_LIMIT`: Maximum number of audit logs to fetch per request (optional, no limit by default)

## Usage

### Basic Usage

Run the exporter with default settings (uses `last_processed.txt` for incremental updates):

```bash
python port_audit_log_exporter.py
```

### Command-Line Arguments

The script supports command-line arguments for flexible time range configuration:

```bash
# Fetch logs starting from a specific date
python port_audit_log_exporter.py --from-date "2025-01-01T00:00:00.000Z"

# Fetch logs within a specific time range
python port_audit_log_exporter.py --from-date "2025-01-01T00:00:00.000Z" --to-date "2025-01-31T23:59:59.999Z"

# Using short form arguments
python port_audit_log_exporter.py -f "2025-01-01T00:00:00.000Z" -t "2025-01-31T23:59:59.999Z"
```

**Note**: Command-line arguments take precedence over environment variables, which take precedence over `last_processed.txt`.

### How It Works

The script will:
1. Parse command-line arguments and environment variables
2. Validate SSL certificates if configured
3. Connect to the Port API with the specified time range
4. Fetch audit logs (no built-in limit unless specified)
5. Send them to the configured Kafka topic with SSL encryption (if enabled)
6. Track the last processed log using `last_processed.txt` (only when not using explicit date ranges)
7. On subsequent runs without date arguments, only process logs newer than the last processed timestamp

### Time Range Priority

The script determines the time range using the following priority order:
1. **Command-line arguments** (`--from-date`, `--to-date`) - highest priority
2. **Environment variables** (`FROM_DATE`, `TO_DATE`)
3. **Last processed file** (`last_processed.txt`) - lowest priority, for backward compatibility

## Architecture
![architecture](https://github.com/port-experimental/audit-logs-to-kafka/blob/main/architecture.png)

## Features

- **Secure Kafka Integration**: SSL client certificate authentication for secure data transmission
- **Flexible Time Range Configuration**: Define time ranges via CLI arguments or environment variables
- **No Built-in Audit Limit**: Fetch all available audit logs without artificial restrictions (optional configurable limit)
- **Consistent Timestamp Handling**: ISO 8601 format with timezone awareness (UTC)
- **Incremental Processing**: Tracks last processed log's timestamp to avoid duplicates
- **Backward Compatible**: Maintains compatibility with existing `last_processed.txt` files
- **Comprehensive Error Handling**: Validates SSL certificates, date formats, API responses, and Kafka connections
- **Priority-based Configuration**: CLI args override environment variables, which override the last processed file
- **Real-time Log Streaming**: Sends logs to Kafka as they are fetched from Port.io

## Log Format

Logs are sent to Kafka in the same format as the [Port Audit Log API](https://docs.port.io/api-reference/get-audit-logs/), typically including:
```json
{
  "identifier": "",
  "action": "",
  "resourceType": "",
  "trigger": {
    "at": "Z",
    "by": {
      "userId": "",
      "orgId": ""
    },
    "origin": ""
  },
  "context": {
    "blueprintId": "",
    "blueprint": "",
    "entityId": "",
    "entity": ""
  },
  "diff": {
    "before": {
      "blueprint": "",
      "identifier": "",
      "createdAt": "",
      "updatedBy": "",
      "createdBy": "",
      "icon": "",
      "title": "",
      "relations": {},
      "properties": {
        "name": null,
        "id": null
      },
      "updatedAt": ""
    },
    "after": {
      "blueprint": "",
      "identifier": "",
      "createdAt": "",
      "updatedBy": "",
      "createdBy": "",
      "icon": "",
      "title": "",
      "relations": {},
      "properties": {
        "name": null,
        "id": null
      },
      "updatedAt": ""
    }
  },
```
