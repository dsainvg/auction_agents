"""Centralized model configuration.

Change values here to alter model parameters used across the project.
"""
MODEL_NAME = "deepseek-ai/deepseek-v3.1"
TEMPERATURE = 0.05
TOP_P = 0.9
MAX_TOKENS = 8192
EXTRA_BODY = {"chat_template_kwargs": {"thinking": True}}
WAIT_BETWEEN_REQUESTS = 2.5

# Structured output class is set where used; keep config minimal and simple.
