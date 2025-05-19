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
        "parameters": {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "items": { "type": "string" },
                    "description": "Each question the operator must answer"
                }
            },
            "required": ["questions"]
        }
    },
    {
        "name": "compose_reply",
        "description": "Return the final customer-facing reply.",
        "parameters": {
            "type": "object",
            "properties": {
                "draft": {"type": "string", "description": "The complete reply text, ready to send or translate."}
            },
            "required": ["draft"]
        }
    }
]

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def run_llm(messages, api_key, functions=None, function_call="auto"):
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=messages,
        functions=functions,
        function_call=function_call,
        temperature=0.9,
        max_tokens=650
    )
    return response.choices[0].message

# ----------------------------------------------------------------------
# Session‑state defaults
# ----------------------------------------------------------------------
def init_state():
    defaults = {
        "stage": "init",        # init, asked, done
        "questions": [],         # list of questions from LLM
        "answers": {},           # operator answers mapping
        "draft": "",
        "translation": "",
        "mode": "Simple",
        "operator_notes": "",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_state()

# ----------------------------------------------------------------------
# UI Inputs
# ----------------------------------------------------------------------
st.radio("Interface mode", ["Simple", "Advanced"], key="mode", horizontal=True)
client_review = st.text_area("Customer message or review", placeholder="Paste the customer's text here", height=140)
st.text_area("Additional information for answer (operator notes)", key="operator_notes", placeholder="Reply to open questions or add facts the model needs.", height=100)
st.radio("Response channel", ["Email (private)", "Public post"], key="channel_type", horizontal=True)
api_key = st.text_input("OpenAI API key", type="password")

# ----------------------------------------------------------------------
# Generate or continue
# ----------------------------------------------------------------------
if st.button("Generate response draft", type="primary"):
    if not client_review.strip() or not api_key:
        st.error("Please provide the customer text and an API key.")
    else:
        # build system prompt
        mode = st.session_state.mode
        preamble = (
            "You are Empathos, a life-insurance support assistant.\n"
            "• First analyse the customer’s message in detail.\n"
            "• Check whether each factual claim can be verified from the operator notes.\n"
            "• If any critical fact is missing or unconfirmed, call request_additional_info with concrete questions.\n"
            "• When everything needed is present, call compose_reply with the final draft.\n"
            "Do not invent promises. All commitments must be explicitly confirmed by operator input."
        )
        if mode == "Simple":
            preamble += "\nIn simple mode, assume the operator cannot be contacted; prefer a minimal answer and do not call request_additional_info."
        messages = [
            {"role": "system", "content": preamble},
            {"role": "user", "content": f"Customer review:\n{client_review}\n\nOperator notes:\n{st.session_state.operator_notes or '-'}"}
        ]
        # first call
        msg = run_llm(messages, api_key, functions=FUNCTIONS)
        if msg.function_call:
            name = msg.function_call.name
            args = json.loads(msg.function_call.arguments)
            if name == "request_additional_info" and mode == "Advanced":
                st.session_state.questions = args.get("questions", [])
                st.session_state.stage = "asked"
            elif name == "compose_reply":
                st.session_state.draft = args.get("draft", "").strip()
                st.session_state.stage = "done"
            else:
                # fallback to treating as draft
                st.session_state.draft = args.get("draft", "").strip()
                st.session_state.stage = "done"
        else:
            st.session_state.draft = msg.content.strip()
            st.session_state.stage = "done"

# ----------------------------------------------------------------------
# If questions are asked, collect answers
# ----------------------------------------------------------------------
if st.session_state.stage == "asked":
    st.header("Operator follow‑up questions")
    for i, q in enumerate(st.session_state.questions):
        ans = st.text_input(f"Q{i+1}: {q}", key=f"ans_{i}")
        st.session_state.answers[q] = ans
    if st.button("Submit answers and draft reply"):
        # append function call with answers
        func_call = {
            "name": "request_additional_info",
            "arguments": json.dumps({"questions": st.session_state.questions,
                                      "answers": st.session_state.answers})
        }
        messages.append({"role": "function", **func_call})
        # resend
        msg = run_llm(messages, api_key, functions=FUNCTIONS)
        if msg.function_call and msg.function_call.name == "compose_reply":
            args = json.loads(msg.function_call.arguments)
            st.session_state.draft = args.get("draft", "").strip()
        else:
            st.session_state.draft = msg.content.strip()
        st.session_state.stage = "done"

# ----------------------------------------------------------------------
# Display draft and translation if done
# ----------------------------------------------------------------------
if st.session_state.stage == "done":
    st.header("Draft response")
    st.text_area("Editable draft response", key="draft_edit", value=st.session_state.draft, height=220)
    default_lang = "English"
    target_lang = st.selectbox("Translate final reply to:", LANGUAGE_OPTIONS, index=LANGUAGE_OPTIONS.index(default_lang))
    if st.button("Translate & update"):
        trans_prompt = f"Translate the reply into {target_lang} using accurate insurance terminology while keeping tone and meaning."
        client = OpenAI(api_key=api_key)
        trans = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role":"system","content":trans_prompt}, {"role":"user","content":st.session_state.draft}],
            max_tokens=1000,
            temperature=0
        )
        st.session_state.translation = trans.choices[0].message.content.strip()

if st.session_state.translation:
    st.header("Translated response")
    st.text_area("Final translation of reply", key="translated_output", value=st.session_state.translation, height=220)
