"""Tests for observability primitives."""
from __future__ import annotations

import io
import json
import unittest

import structlog


class StructuredLoggingTests(unittest.TestCase):
    def test_json_output_to_buffer(self):
        from app.observability import configure_logging, get_logger

        # Capture stdout
        import sys

        old = sys.stdout
        buf = io.StringIO()
        sys.stdout = buf
        try:
            configure_logging("INFO")
            log = get_logger("test")
            log.info("test_event", foo="bar", n=42)
        finally:
            sys.stdout = old
        line = buf.getvalue().strip()
        # Each line is JSON
        data = json.loads(line)
        self.assertEqual(data["event"], "test_event")
        self.assertEqual(data["foo"], "bar")
        self.assertEqual(data["n"], 42)
        self.assertIn("timestamp", data)
        self.assertEqual(data["level"], "info")

    def test_log_level_filtering(self):
        import io
        import sys

        from app.observability import configure_logging, get_logger

        old = sys.stdout
        buf = io.StringIO()
        sys.stdout = buf
        try:
            configure_logging("WARNING")
            log = get_logger("test")
            log.info("info_msg_should_be_filtered")
            log.warning("warn_msg_should_appear")
        finally:
            sys.stdout = old
        out = buf.getvalue()
        self.assertNotIn("info_msg_should_be_filtered", out)
        self.assertIn("warn_msg_should_appear", out)


class MetricsTests(unittest.TestCase):
    def test_metrics_endpoint_returns_prometheus_format(self):
        """The /metrics endpoint should return Prometheus text format."""
        from app.observability import render_metrics

        body, content_type = render_metrics()
        # The body should contain at least one of our metric names
        # (it will be empty if no metrics have been recorded yet,
        # but the format must be valid)
        self.assertIsInstance(body, bytes)
        self.assertIn("text/plain", content_type)

    def test_metrics_incremented(self):
        """Verify that incrementing a counter shows up in output."""
        from app.observability import HTTP_REQUESTS_TOTAL, render_metrics

        before = render_metrics()[0].decode()
        HTTP_REQUESTS_TOTAL.labels(method="GET", path="/test", status="200").inc()
        after = render_metrics()[0].decode()
        # After should contain the metric name (and a new sample)
        self.assertIn("mimicguard_http_requests_total", after)
        # The total count for that label set should have increased
        self.assertNotEqual(before, after)
