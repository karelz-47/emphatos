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
                "questions": {"type": "array", "items": {"type": "string"}, "description": "Each question the operator must answer"}
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

# ----------------------------------------------------------------------
# Initialize session state
# ----------------------------------------------------------------------
def init_state():
    defaults = {
        "stage": "init",  # init, asked, done, reviewed, translated, reviewed_translation
        "questions": [],
        "answers": {},
        "draft": "",
        "reviewed_draft": "",
        "translation": "",
        "reviewed_translation": "",
        "mode": "Simple",
        "operator_notes": "",
        "messages": []
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
# Button actions
# ----------------------------------------------------------------------
# Generate draft
if st.button("Generate response draft", key="btn_generate"):
    if not client_review.strip() or not api_key:
        st.error("Please provide the customer text and an API key.")
    else:
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
        msgs = [
            {"role": "system", "content": preamble},
            {"role": "user", "content": f"Customer review:\n{client_review}\n\nOperator notes:\n{st.session_state.operator_notes or '-'}"}
        ]
        st.session_state.messages = msgs
        # call LLM differently based on mode
        if mode == "Simple":
            msg = run_llm(msgs, api_key)
        else:
            msg = run_llm(msgs, api_key, functions=FUNCTIONS)

        # handle LLM response
        if hasattr(msg, 'function_call') and msg.function_call:
            fn = msg.function_call.name
            args = json.loads(msg.function_call.arguments or "{}")
            if fn == "request_additional_info" and mode == "Advanced":
                st.session_state.questions = args.get("questions", [])
                st.session_state.stage = "asked"
            else:
                st.session_state.draft = (args.get("draft") or msg.content or "").strip()
                st.session_state.stage = "done"
        else:
            st.session_state.draft = (msg.content or "").strip()
            st.session_state.stage = "done"

# Submit answers
if st.session_state.stage == "asked":
    st.header("Operator follow-up questions")
    for i, q in enumerate(st.session_state.questions):
        ans = st.text_input(f"Q{i+1}: {q}", key=f"ans_{i}")
        st.session_state.answers[q] = ans
    if st.button("Submit answers and draft reply", key="btn_submit_answers"):
        msgs = list(st.session_state.messages)
        msgs.append({
            "role": "function",
            "name": "request_additional_info",
            "content": json.dumps({"questions": st.session_state.questions, "answers": st.session_state.answers})
        })
        st.session_state.messages = msgs
        msg = run_llm(msgs, api_key, functions=FUNCTIONS)
        if hasattr(msg, 'function_call') and msg.function_call.name == "compose_reply":
            st.session_state.draft = json.loads(msg.function_call.arguments or "{}").get("draft", "").strip()
        else:
            st.session_state.draft = (msg.content or "").strip()
        st.session_state.stage = "done"

# ----------------------------------------------------------------------
# Draft review loop
# ----------------------------------------------------------------------
if st.session_state.stage == "done" and not st.session_state.reviewed_draft:
    review_prompt = (
        "You are a thorough supervisor reviewing the draft reply against all instructions."
        " Identify any factual, tone, or promise issues and output a revised draft with corrections."
    )
    review_msgs = [
        {"role": "system", "content": review_prompt},
        {"role": "user", "content": st.session_state.draft or ""}
    ]
    review_msg = run_llm(review_msgs, api_key)
    st.session_state.reviewed_draft = (review_msg.content or "").strip()
    st.session_state.stage = "reviewed"

# Display reviewed draft
if st.session_state.stage in ["reviewed", "translated", "reviewed_translation"]:
    st.header("Reviewed Draft Response")
    st.text_area("Final draft after review", key="draft_edit", value=st.session_state.reviewed_draft, height=220)

# ----------------------------------------------------------------------
# Translation + review
# ----------------------------------------------------------------------
if st.session_state.stage == "reviewed":
    tgt = st.selectbox("Translate final reply to:", LANGUAGE_OPTIONS, index=0)
    if st.button("Translate & review", key="btn_translate"):
        trans = OpenAI(api_key=api_key).chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": f"Translate without empty promises into {tgt}."},
                {"role": "user", "content": st.session_state.reviewed_draft or ""}
            ],
            max_tokens=1000,
            temperature=0
        )
        st.session_state.translation = (trans.choices[0].message.content or "").strip()
        st.session_state.stage = "translated"

if st.session_state.stage == "translated" and not st.session_state.reviewed_translation:
    rev_prompt = (
        "You are a meticulous supervisor reviewing the translated reply for accuracy, tone, and no empty promises."
        " Produce the final translation."
    )
    rev_msgs = [
        {"role": "system", "content": rev_prompt},
        {"role": "user", "content": st.session_state.translation or ""}
    ]
    rev_msg = run_llm(rev_msgs, api_key)
    st.session_state.reviewed_translation = (rev_msg.content or "").strip()
    st.session_state.stage = "reviewed_translation"

# ----------------------------------------------------------------------
# Final translated output
# ----------------------------------------------------------------------
if st.session_state.reviewed_translation:
    st.header("Final Translated Response")
    st.text_area("Final translation after review", key="translated_output", value=st.session_state.reviewed_translation, height=220)
