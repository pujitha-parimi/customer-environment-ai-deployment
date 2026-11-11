"""Prometheus metrics. Labels are low-cardinality and contain no customer data."""
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
IN_PROGRESS = Gauge("http_requests_in_progress", "Requests currently being served")
QUERIES = Counter("support_queries_total", "Support queries by routed category", ["category"])
GEMINI_ERRORS = Counter("gemini_errors_total", "Failed Gemini calls by reason", ["reason"])
AUTH_FAILURES = Counter("auth_failures_total", "Rejected authentication attempts", ["scope"])

__all__ = [n for n in dir() if n.isupper()] + ["generate_latest"]
