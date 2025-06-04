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

def log_run_llm(messages, api_key, functions=None, function_call="auto"):
    """
    Calls run_llm, but also appends a record of outgoing+incoming to st.session_state.api_log.
    """
    # (1) Make a shallow copy of the messages list so we don’t accidentally mutate st.session_state.messages later.
    outgoing_copy = [dict(m) for m in messages]
    # (2) Actually call the API
    response_msg = run_llm(messages, api_key, functions=functions, function_call=function_call)

    # (3) Store both outgoing and incoming in the log
    st.session_state.api_log.append({
        "outgoing": outgoing_copy,
        "incoming": {
            "role": response_msg.role,
            "content": response_msg.content,
            # If function_call is present, log it, too
            "function_call": {
                "name": getattr(response_msg, "function_call", None) and response_msg.function_call.name,
                "arguments": getattr(response_msg, "function_call", None) and response_msg.function_call.arguments
            }
        }
    })

    return response_msg

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
        "messages": [],
        "api_log": []
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

# ───────────────────────────────────────────────────────────────────────
# Button actions
# ───────────────────────────────────────────────────────────────────────
if st.button("Generate response draft", key="btn_generate"):
    if not client_review.strip() or not api_key:
        st.error("Please provide the customer text and an API key.")
    else:
        mode = st.session_state.mode

        # ─── SIMPLE MODE ────────────────────────────────────────────────
        if mode == "Simple":
            # — Stand-alone prompt that always asks for the best answer possible —
            prompt_simple = (
                "You are Empathos, a seasoned life-insurance-support assistant.\n"
               ## Context
                "Customer review (verbatim):\n"
                f"{client_review}\n\n"
                "Operator notes:\n"
                f"{st.session_state.operator_notes or '-'}\n\n"
                ## Instructions
                "Task:\n"
                "1. Write a complete reply to the customer even if some details are missing."
                "2. Whenever you must infer a fact, prefix it with `ASSUMPTION:` and state it in one sentence. \n"
                "3. Length: ≤ 250 words."
                "4. Voice: warm, empathic, strictly factual; never create obligations that are not in Operator notes.\n"
                "5. **Return only the final reply text** – no lists, no meta-commentary.\n"
            )

            # Call LLM with this single, self-contained prompt
            msg = log_run_llm(
                [{"role": "system", "content": prompt_simple}],
                api_key
            )

            # Take whatever GPT returned as the draft—no overrides
            st.session_state.draft = (msg.content or "").strip()
            st.session_state.stage = "done"

        # ─── ADVANCED MODE ──────────────────────────────────────────────
        else:
            # A fully standalone prompt for Advanced mode:
            # - Analyze carefully against operator_notes.
            # - If any fact is missing or unconfirmed, call request_additional_info.
            # - If everything is present, call compose_reply with the final draft.
            # - Never invent promises—only use facts from operator_notes.
            prompt_advanced = (
                "You are Empathos, a seasoned life-insurance-support assistant.\n"
                "Customer review:\n"
                f"{client_review}\n\n"
                "Operator notes:\n"
                f"{st.session_state.operator_notes or '-'}\n\n"
                "Task:\n"
                "1. Carefully analyze the customer’s review against the operator notes.\n"
                "2. If any critical fact is missing or unconfirmed:\n"
                "2.1 Return a numbered list of precise, concrete questions the operator must answer.\n"
                "2.2 Prefix the very first line with 'QUESTIONS:' \n"
                "3. If all critical facts are available:\n"
                "3.1 Draft the complete customer reply (≤ 250 words).\n"
                "3.2 Whenever you must infer a detail, prefix the sentence with 'ASSUMPTION:' \n"
                "3.3 Do not invent any promises—only use facts explicitly confirmed in the operator notes.\n"
                "3.4 Prefix the very first line with 'REPLY:' \n"
                "RULES:\n"
                "– Empathic, professional tone; never promise more than the Operator notes allow.\n"
                "– Do not mention internal processes."
              )

            msg = log_run_llm(
                [{"role": "system", "content": prompt_advanced}],
                api_key,
                functions=FUNCTIONS
            )

            if hasattr(msg, "function_call") and msg.function_call:
                fn = msg.function_call.name
                args = json.loads(msg.function_call.arguments or "{}")

                if fn == "request_additional_info":
                    st.session_state.questions = args.get("questions", [])
                    st.session_state.stage = "asked"
                    st.stop()

                elif fn == "compose_reply":
                    st.session_state.draft = (args.get("draft") or "").strip()
                    st.session_state.stage = "done"

                else:
                    # (Fallback—shouldn’t happen if model obeys the prompt exactly)
                    st.session_state.draft = (msg.content or "").strip()
                    st.session_state.stage = "done"

            else:
                # If the model didn’t call a function, treat its content as a draft
                st.session_state.draft = (msg.content or "").strip()
                st.session_state.stage = "done"

# ----------------------------------------------------------------------
# Draft review loop (only return the corrected draft, no commentary)
# ----------------------------------------------------------------------
if st.session_state.stage == "done" and not st.session_state.reviewed_draft:
    review_prompt = (
        "You are a strict reviewer.  \n"
        "TASK:\n"
        "– Audit the draft for factual accuracy, tone, and unauthorized promises.\n"
        "– Correct any issues directly in-line.\n"
        "– Delete or rewrite ASSUMPTION lines only if they are unsupported or unclear.\n"
        "– Keep total length no more than 250 words.\n"
        "- Return only the corrected draft; no explanations or reviewer notes.\n"
        "**Output only the final, corrected draft** (no explanations or reviewer notes)."
    )
    review_msgs = [
        {"role": "system", "content": review_prompt},
        {"role": "user", "content": st.session_state.draft or ""}
    ]
    review_msg = log_run_llm(review_msgs, api_key)
    # The model will now return just the “clean” draft.
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
        # Build a simple translate‐only prompt
        trans_prompt = (
            f"Translate the following reply into {tgt} while: \n"
            "REQUIREMENTS: \n"
            "1. Keep meaning, tone, and sentence count identical where possible.\n"
            "2. Do not add promises or commentary.\n"
            "3. All subsequent reviews must remain in {tgt}.\n"
            f"{st.session_state.reviewed_draft}"
        )
        msgs_trans = [
            {"role": "system", "content": trans_prompt}
        ]
        # Use run_llm so the result lands in st.session_state.translation
        msg_trans = log_run_llm(msgs_trans, api_key)
        st.session_state.translation = (msg_trans.content or "").strip()
        st.session_state.stage = "translated"

if st.session_state.stage == "translated" and not st.session_state.reviewed_translation:
    # Prompt the LLM to double-check the translation for accuracy, tone, and no empty promises
    rev_prompt = (
        "You are a meticulous supervisor reviewing the translated reply.\n"
        "TASK:\n"
        "1. Polish the translated reply for accuracy, tone, and removal of empty promises.\n"
        "2. Minor wording tweaks only; preserve structure.\n"
        "3. Return the final translation, in the same language it already uses – nothing else."
    )
    rev_msgs = [
        {"role": "system", "content": rev_prompt},
        {"role": "user", "content": st.session_state.translation or ""}
    ]
    rev_msg = log_run_llm(rev_msgs, api_key)
    st.session_state.reviewed_translation = (rev_msg.content or "").strip()
    st.session_state.stage = "reviewed_translation"

# ----------------------------------------------------------------------
# Final translated output
# ----------------------------------------------------------------------
if st.session_state.reviewed_translation:
    st.header("Final Translated Response")
    st.text_area("Final translation after review", key="translated_output", value=st.session_state.reviewed_translation, height=220)

# ───────────────────────────────────────────────────────────────────────
# Debug: show full API log at bottom
# ───────────────────────────────────────────────────────────────────────
if st.session_state.api_log:
    st.markdown("---")
    st.markdown("## 🔍 API Communication Log (all calls)")
    for i, entry in enumerate(st.session_state.api_log, start=1):
        with st.expander(f"Call #{i}"):
            st.markdown("**Outgoing messages**:")
            for m in entry["outgoing"]:
                st.write(f"- role: `{m['role']}`")
                st.write(f"  ```\n{m['content']}\n```")
            st.markdown("**Incoming response**:")
            inc = entry["incoming"]
            st.write(f"- role: `{inc['role']}`")
            st.write("```")
            st.write(f"{inc['content']}")
            st.write("```")
            if inc.get("function_call") and inc["function_call"]["name"]:
                st.markdown("- function_call:")
                st.write(f"  - name: `{inc['function_call']['name']}`")
                st.write("  - arguments:")
                st.json(json.loads(inc["function_call"]["arguments"] or "{}"))
