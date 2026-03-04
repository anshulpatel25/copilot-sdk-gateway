"""Prometheus business metrics for copilot-sdk-gateway."""

from prometheus_client import Counter, Histogram

completions_total = Counter(
    "completions_total",
    "Total number of successful completions",
    ["model", "endpoint"],
)

prompt_length_chars = Histogram(
    "prompt_length_chars",
    "Length of prompt in characters",
    ["endpoint"],
)

response_length_chars = Histogram(
    "response_length_chars",
    "Length of response in characters",
    ["endpoint"],
)
