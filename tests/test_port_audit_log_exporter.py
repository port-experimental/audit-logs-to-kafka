import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
from datetime import datetime
import dateutil.parser
import os
import sys

# Mock the kafka module
sys.modules['kafka'] = MagicMock()
from port_audit_log_exporter import (
    get_last_processed_time,
    save_last_processed_time,
    add_one_second
)

class TestPortAuditLogExporter(unittest.TestCase):
    def setUp(self):
        # Sample test data
        self.sample_timestamp = "2024-04-23T12:00:00.000Z"
        self.sample_logs = {
            "ok": True,
            "audits": [
                {
                    "trigger": {
                        "at": self.sample_timestamp
                    },
                    "data": "test log data"
                }
            ]
        }

    def test_get_last_processed_time(self):
        # Test when file exists
        with patch("builtins.open", mock_open(read_data=self.sample_timestamp)):
            result = get_last_processed_time()
            self.assertEqual(result, self.sample_timestamp)

        # Test when file doesn't exist
        with patch("builtins.open", mock_open()) as mock_file:
            mock_file.side_effect = FileNotFoundError
            result = get_last_processed_time()
            self.assertIsNone(result)

    def test_save_last_processed_time(self):
        with patch("builtins.open", mock_open()) as mock_file:
            save_last_processed_time(self.sample_timestamp)
            mock_file.assert_called_once_with('last_processed.txt', 'w')
            mock_file().write.assert_called_once_with(self.sample_timestamp)

    def test_add_one_second(self):
        # Test adding one second
        result = add_one_second(self.sample_timestamp)
        original_dt = dateutil.parser.parse(self.sample_timestamp)
        result_dt = dateutil.parser.parse(result)
        
        # Check that the difference is exactly 1 second
        self.assertEqual((result_dt - original_dt).total_seconds(), 1)
        
        # Check that the format is correct
        self.assertTrue(result.endswith("Z"))
        self.assertTrue("." in result)  # Should have milliseconds
        
        # Test the milliseconds format
        self.assertRegex(result, r"\.\d{3}Z$")  # Should end with exactly 3 decimal places

    @patch('requests.get')
    @patch('kafka.KafkaProducer')
    def test_api_response_handling(self, mock_kafka_producer, mock_requests_get):
        # Set up environment variables
        with patch.dict(os.environ, {
            'PORT_API_TOKEN': 'test-token',
            'PORT_API_URL': 'https://api.test.io',
            'KAFKA_SERVER': 'localhost:9092',
            'KAFKA_TOPIC': 'test-topic'
        }):
            # Mock the API response
            mock_response = MagicMock()
            mock_response.json.return_value = self.sample_logs
            mock_requests_get.return_value = mock_response

            # Mock the Kafka producer
            mock_producer = MagicMock()
            mock_kafka_producer.return_value = mock_producer

            # Run the script with mocked file operations
            with patch('builtins.open', mock_open(read_data=self.sample_timestamp)) as mock_file:
                import importlib
                import port_audit_log_exporter
                importlib.reload(port_audit_log_exporter)

            # Verify API call
            mock_requests_get.assert_called_once_with(
                f"https://api.test.io/v1/audit-log?limit=1000&from={self.sample_timestamp}",
                headers={
                    "Authorization": "test-token",
                    "Content-Type": "application/json"
                }
            )

            # Verify Kafka producer was initialized and used correctly
            mock_kafka_producer.assert_called_once_with(
                bootstrap_servers='localhost:9092',
                value_serializer=mock_kafka_producer.call_args[1]['value_serializer']
            )
            
            # Verify the log was sent to Kafka
            mock_producer.send.assert_called_once_with('test-topic', self.sample_logs['audits'][0])
            mock_producer.flush.assert_called_once()

if __name__ == '__main__':
    unittest.main() 