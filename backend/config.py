"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Council members - list of OpenRouter model identifiers
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# ===== Supreme Court Configuration =====

# Supreme Court Justices - 9 premier models
SUPREME_COURT_JUSTICES = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
    "meta-llama/llama-4-maverick",
    "mistralai/mistral-large-2411",
    "deepseek/deepseek-chat-v3-0324",
    "qwen/qwen-max",
    "ai21/jamba-1.6-large",
]

# Model power rankings (for selecting group leads)
# Higher number = more powerful, used to select majority/minority leads
MODEL_POWER_RANKINGS = {
    "openai/gpt-5.1": 10,
    "google/gemini-3-pro-preview": 9,
    "anthropic/claude-sonnet-4.5": 9,
    "x-ai/grok-4": 8,
    "meta-llama/llama-4-maverick": 8,
    "mistralai/mistral-large-2411": 7,
    "deepseek/deepseek-chat-v3-0324": 8,
    "qwen/qwen-max": 7,
    "ai21/jamba-1.6-large": 6,
}

# Clerk model - responsible for analyzing responses and grouping justices
CLERK_MODEL = "google/gemini-2.5-flash"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
