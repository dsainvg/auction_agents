"""Centralized model configuration.

Change values here to alter model parameters used across the project.
"""
MODEL_NAME = "deepseek-ai/deepseek-v3.1-terminus"
TEMPERATURE = 0.15
TOP_P = 0.7
MAX_TOKENS = 8192
EXTRA_BODY = {"chat_template_kwargs": {"thinking":True}}
WAIT_BETWEEN_REQUESTS = 2 # seconds

# Structured output class is set where used; keep config minimal and simple.
