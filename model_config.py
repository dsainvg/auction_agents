"""Centralized model configuration.

Change values here to alter model parameters used across the project.
"""
MODEL_NAME = "deepseek-ai/deepseek-v3.1"
TEMPERATURE = 0.15
TOP_P = 0.7
MAX_TOKENS = 11617
EXTRA_BODY = {"chat_template_kwargs": {"thinking":True}}
WAIT_BETWEEN_REQUESTS = 0.6 # seconds - optimized for 40 requests/minute limit (60/35 = 1.71s)

# Structured output class is set where used; keep config minimal and simple.
