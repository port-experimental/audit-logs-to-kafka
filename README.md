# Port.io Audit Log Exporter

This script exports audit logs from Port.io to a Kafka stream for SIEM ingestion. It tracks the last processed log to ensure only new logs are exported.

## Prerequisites

- Python 3.7+
- Kafka cluster
- Port.io API access and token
- python-dateutil package

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

```
PORT_API_TOKEN=Bearer your_token_here
PORT_API_URL=https://api.getport.io/v1
KAFKA_SERVER=localhost:9092
KAFKA_TOPIC=port-logs
```

- `PORT_API_TOKEN`: Your Port.io API token with "Bearer " prefix
- `PORT_API_URL`: The Port.io API endpoint (default: https://api.getport.io/v1)
- `KAFKA_SERVER`: Kafka broker address (default: localhost:9092)
- `KAFKA_TOPIC`: Kafka topic to send logs to (default: port-logs)

## Usage

Run the exporter:
```bash
python port_audit_log_exporter.py
```

The script will:
1. Connect to Port.io API
2. Fetch audit logs
3. Send them to the configured Kafka topic
4. Track the last processed log using `last_processed.txt`
5. On subsequent runs, only process logs newer than the last processed timestamp

## Features

- Tracks last processed log's timestamp to avoid duplicates
- Uses Port.io's audit log API
- Sends logs to Kafka in real-time
- Handles API pagination with limit parameter

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