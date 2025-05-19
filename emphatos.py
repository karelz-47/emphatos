import re
import json
import streamlit as st
from openai import OpenAI

# ----------------------------------------------------------------------
# Page config
# ----------------------------------------------------------------------
st.set_page_config(page_title="Empathos v4.0", layout="centered")
st.title("Empathos")
st.subheader("Your voice, their peace of mind")

# ----------------------------------------------------------------------
# Constants & function schemas
# ----------------------------------------------------------------------
LANGUAGE_OPTIONS = [
    "English", "Slovak", "Italian", "Icelandic",
    "Hungarian", "German", "Czech", "Polish", "Vulcan"
]

FUNCTIONS = [
    {
        "name": "request_additional_info",
        "description": "Ask the operator for missing facts or confirmations before a customer reply can be written.",
        "parameters": {"type": "object","properties": {"questions": {"type": "array","items": {"type": "string"},"description": "Each question the operator must answer"}},"required": ["questions"]}
    },
    {
        "name": "compose_reply",
        "description": "Return the final customer-facing reply.",
        "parameters": {"type": "object","properties": {"draft": {"type": "string","description": "The complete reply text, ready to send or translate."}},"required": ["draft"]}
    }
]

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------

def run_llm(messages, api_key, functions=None, function_call="auto"):
    client = OpenAI(api_key=api_key)
    # Build kwargs dynamically: only include functions & function_call if functions provided
    params = {
        "model": "gpt-4.1",
        "messages": messages,
        "temperature": 0.9,
        "max_tokens": 650
    }
    if functions:
        params["functions"] = functions
        params["function_call"] = function_call
    response = client.chat.completions.create(**params)
    return response.choices[0].message
