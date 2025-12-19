"""Centralized model configuration.

Change values here to alter model parameters used across the project.
"""
MODEL_NAME = "qwen/qwen3-235b-a22b"
TEMPERATURE = 0.2
TOP_P = 0.7
MAX_TOKENS = 4096
EXTRA_BODY = {"chat_template_kwargs": {"thinking": True}}
WAIT_BETWEEN_REQUESTS = 5 # seconds

# Structured output class is set where used; keep config minimal and simple.
