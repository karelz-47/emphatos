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
                    "items": {"type": "string"},
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
                "draft": {
                    "type": "string",
                    "description": "The complete reply text, ready to send or translate."
                }
            },
            "required": ["draft"]
        }
    }
]

DEFAULT_PROMPT_ADVANCED = (
    "You are Empathos, a seasoned life-insurance-support assistant.\n"
    "Use professional unit-linked insurance terminology; ensure it sounds natural for native speakers with a background in unit-linked insurance.\n"
    "Customer review:\n"
    "{client_review}\n\n"
    "Operator notes:\n"
    "{operator_notes}\n\n"
    "Task:\n"
    "1. Carefully analyze the customer’s review against the operator notes.\n"
    "2. If any critical fact is missing or unconfirmed:\n"
    "   2.1 Return a numbered list of precise, concrete questions. Prefix the first line with 'QUESTIONS:'\n"
    "3. If all critical facts are available:\n"
    "   3.1 Draft the complete customer reply (≤ 250 words). Prefix the first line with 'REPLY:'\n"
    "   3.2 Whenever you must infer a detail, prefix the sentence with 'ASSUMPTION:'\n"
    "   3.3 Do not invent any promises—only use facts explicitly confirmed in the operator notes.\n"
    "4. At the end of your reply, include exactly this signature (do not alter it):\n"
    "{signature}\n"
    "RULES:\n"
    "– Empathic, professional tone; never promise more than the operator notes allow.\n"
    "– Do not mention internal processes."
)

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
    outgoing_copy = [dict(m) for m in messages]
    response_msg = run_llm(messages, api_key=api_key, functions=functions, function_call=function_call)

    st.session_state.api_log.append({
        "outgoing": outgoing_copy,
        "incoming": {
            "role": response_msg.role,
            "content": response_msg.content,
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
        "stage": "init",            # init, asked, done, reviewed, translated, reviewed_translation
        "questions": [],            # list of strings
        "answers": {},              # mapping "q0"→answer_text, "q1"→answer_text, ...
        "draft": "",
        "reviewed_draft": "",
        "translation": "",
        "reviewed_translation": "",
        "mode": "Simple",           # "Simple" or "Advanced"
        "operator_notes": "",
        "signature": "",            # operator’s personal signature line
        "messages": [],             # full chat history
        "api_log": []               # list of {"outgoing": [...], "incoming": {...}}
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


init_state()


# ----------------------------------------------------------------------
# UI Inputs
# ----------------------------------------------------------------------

# (1) Enable/disable function-calling (Advanced only)
use_functions = st.checkbox("Enable function-calling (Advanced only)", value=True)
st.session_state.use_functions = use_functions

# (2) Reply style selector
tone = st.selectbox(
    "Reply style",
    ["Empathic", "Concise", "Detailed", "Strictly professional"],
    index=0
)
st.session_state.tone = tone

# (3) Signature input
st.text_area(
    "Operator signature (e.g., 'Yours sincerely\nJacob')",
    key="signature",
    placeholder="Enter your personal signature line(s) here",
    height=80
)

# (4) Auto-detect & translate customer message
detect_translate = st.checkbox("Auto-detect customer language and translate to English", key="auto_detect")

# (5) Interface mode: Simple vs. Advanced
st.radio("Interface mode", ["Simple", "Advanced"], key="mode", horizontal=True)

# (6) Customer message / review (always editable)
client_review = st.text_area(
    "Customer message or review",
    placeholder="Paste the customer's text here",
    height=140
)

# (7) Operator notes (always editable)
st.text_area(
    "Additional information for answer (operator notes)",
    key="operator_notes",
    placeholder="Reply to open questions or add facts the model needs.",
    height=100
)

# (8) Response channel: Email (private) or Public post
st.radio("Response channel", ["Email (private)", "Public post"], key="channel_type", horizontal=True)

# (9) API key input
api_key = st.text_input("OpenAI API key", type="password")


# ───────────────────────────────────────────────────────────────────────
# Button: "Clear fields / Start new task"
# ───────────────────────────────────────────────────────────────────────
st.markdown("---")
preserve_info = st.checkbox("Keep signature and notes when clearing", key="keep_info")
if st.button("Clear fields / Start new task", key="btn_clear"):
    # Optionally preserve operator_notes and signature
    if preserve_info:
        saved_signature = st.session_state.signature
        saved_notes = st.session_state.operator_notes
    # Clear everything except tone, use_functions, detect_translate (and maybe preserve)
    for k in [
        "stage", "questions", "answers", "draft", "reviewed_draft",
        "translation", "reviewed_translation", "messages", "api_log"
    ]:
        if isinstance(st.session_state.get(k), str):
            st.session_state[k] = ""
        else:
            st.session_state[k] = [] if isinstance(st.session_state[k], list) else {}
    st.session_state.mode = "Simple"
    if preserve_info:
        st.session_state.signature = saved_signature
        st.session_state.operator_notes = saved_notes
    else:
        st.session_state.signature = ""
        st.session_state.operator_notes = ""
    st.experimental_rerun()


st.markdown("---")


# ───────────────────────────────────────────────────────────────────────
# Button actions: "Generate response draft"
# ───────────────────────────────────────────────────────────────────────
if st.button("Generate response draft", key="btn_generate"):
    # Validate required fields
    if not client_review.strip() or not api_key:
        st.error("Please provide the customer text and an API key.")
    else:
        # (A) If auto-detect is on, translate the incoming review into English first
        if detect_translate:
            try:
                detect_prompt = (
                    "You are a translation assistant. Detect the language of the following text, "
                    "then translate it into English. Return only the English translation."
                )
                resp = run_llm(
                    [
                        {"role": "system", "content": detect_prompt},
                        {"role": "user", "content": client_review}
                    ],
                    api_key
                )
                client_review_en = resp.content.strip()
            except Exception as e:
                st.error(f"❌ OpenAI API error (translation): {e}")
                st.stop()
        else:
            client_review_en = client_review

        # (B) Build channel‐specific instructions
        if st.session_state.channel_type == "Email (private)":
            channel_instr = (
                "Format the response as a private email: "
                "greet the customer by name if known, include a polite signature, "
                "and keep policy references internal."
            )
        else:
            channel_instr = (
                "Format the response as a public-facing post: no personal details, "
                "concise, maintain brand voice, end with a call-to-action if appropriate."
            )

        mode = st.session_state.mode
        signature = st.session_state.signature.strip() or "(No signature provided)"

        # ─── SIMPLE MODE ────────────────────────────────────────────────
        if mode == "Simple":
            prompt_simple = (
                f"{channel_instr}\n"
                "You are Empathos, a seasoned life-insurance-support assistant.\n"
                "Use professional unit-linked insurance terminology; ensure it sounds natural for native speakers with a background in unit-linked insurance.\n"
                f"Style: {st.session_state.tone}\n"
                "Customer review (verbatim):\n"
                f"{client_review_en}\n\n"
                "Operator notes:\n"
                f"{st.session_state.operator_notes or '-'}\n\n"
                "Task:\n"
                "1. Write a complete reply to the customer even if some details are missing.\n"
                "2. Whenever you must infer a fact, prefix it with `ASSUMPTION:` in one sentence.\n"
                "3. Length: ≤ 250 words.\n"
                "4. Voice: warm, empathic, strictly factual, using unit-linked insurance terminology appropriately.\n"
                "5. At the end of your reply, include exactly this signature (do not alter it):\n"
                f"{signature}\n"
                "6. **Return only the final reply text** – no lists, no meta-commentary.\n"
            )

            # Append system prompt to the message-history
            st.session_state.messages.append({
                "role": "system",
                "content": prompt_simple
            })

            # Call the LLM (no function-calling in Simple mode)
            try:
                msg = log_run_llm(
                    st.session_state.messages,
                    api_key
                )
            except Exception as e:
                st.error(f"❌ OpenAI API error: {e}")
                st.stop()

            # Append assistant response to the history
            st.session_state.messages.append({
                "role": msg.role,
                "content": msg.content,
                "function_call": getattr(msg, "function_call", None)
            })

            # Store draft and advance stage
            st.session_state.draft = (msg.content or "").strip()
            st.session_state.stage = "done"

        # ─── ADVANCED MODE ──────────────────────────────────────────────
        else:
            # (C) Initialize or recall custom prompt
            if "custom_prompt" not in st.session_state:
                st.session_state.custom_prompt = DEFAULT_PROMPT_ADVANCED

            # (D) Allow the user to inspect/edit that system prompt
            with st.expander("🔑 View/Edit system prompt"):
                prompt_advanced_temp = st.text_area(
                    "System prompt (Advanced mode)",
                    value=st.session_state.custom_prompt,
                    height=200
                )
                st.session_state.custom_prompt = prompt_advanced_temp

            # (E) Fill in placeholders for advanced mode
            prompt_advanced = st.session_state.custom_prompt.format(
                client_review=client_review_en,
                operator_notes=st.session_state.operator_notes or "-",
                signature=signature
            )

            # Prepend channel_instr and tone
            prompt_advanced = (
                f"{channel_instr}\n"
                f"{prompt_advanced}"
            )

            # Append to history
            st.session_state.messages.append({
                "role": "system",
                "content": prompt_advanced
            })

            # Call LLM, using functions if enabled
            if st.session_state.use_functions:
                try:
                    msg = log_run_llm(
                        st.session_state.messages,
                        api_key,
                        functions=FUNCTIONS
                    )
                except Exception as e:
                    st.error(f"❌ OpenAI API error: {e}")
                    st.stop()
            else:
                try:
                    msg = log_run_llm(
                        st.session_state.messages,
                        api_key,
                        functions=None
                    )
                except Exception as e:
                    st.error(f"❌ OpenAI API error: {e}")
                    st.stop()

            # Append assistant response to the history
            st.session_state.messages.append({
                "role": msg.role,
                "content": msg.content,
                "function_call": getattr(msg, "function_call", None)
            })

            # (F) Process function calls if any
            if getattr(msg, "function_call", None):
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
                    # Fallback if something unexpected happened
                    st.session_state.draft = (msg.content or "").strip()
                    st.session_state.stage = "done"
            else:
                # If no function_call, treat `msg.content` as the draft
                st.session_state.draft = (msg.content or "").strip()
                st.session_state.stage = "done"


# ───────────────────────────────────────────────────────────────────────
# [1] Show questions & collect operator answers (Advanced “asked” stage)
# ───────────────────────────────────────────────────────────────────────
if st.session_state.stage == "asked":
    st.header("⚙️ Additional Information Needed")

    # (G) “Edit operator notes” button
    if st.button("↶ Edit operator notes", key="btn_edit_notes"):
        st.session_state.stage = "init"
        st.session_state.questions = []
        st.session_state.answers = {}
        st.experimental_rerun()

    st.markdown(
        "The model needs more facts before drafting a reply. "
        "Please answer each of the questions below:"
    )

    # Render one text_area per question
    answers = {}
    for i, q in enumerate(st.session_state.questions):
        key = f"answer_{i}"
        answers[key] = st.text_area(f"Q{i+1}: {q}", key=key, height=80)

    if st.button("Submit additional info", key="btn_submit_info"):
        missing = [
            i for i in range(len(st.session_state.questions))
            if not answers[f"answer_{i}"].strip()
        ]
        if missing:
            st.error("Please answer all the questions before continuing.")
        else:
            st.session_state.answers = {
                f"q{i}": answers[f"answer_{i}"].strip()
                for i in range(len(st.session_state.questions))
            }

            # Rebuild context to call compose_reply
            msgs = []
            prompt_advanced = (
                "You are Empathos, a seasoned life-insurance-support assistant.\n"
                "Use professional unit-linked insurance terminology; ensure it sounds natural for native speakers with a background in unit-linked insurance.\n"
                f"Customer review:\n{st.session_state.messages[0]['content']}\n\n"
                f"Operator notes:\n{st.session_state.operator_notes or '-'}\n\n"
                "Task:\n"
                "1. These are the additional facts provided by the operator:\n"
            )
            msgs.append({"role": "system", "content": prompt_advanced})

            for i, q in enumerate(st.session_state.questions):
                answer_text = st.session_state.answers[f"q{i}"]
                msgs.append({
                    "role": "user",
                    "content": f"Q: {q}\nA: {answer_text}"
                })

            compose_call = {
                "name": "compose_reply",
                "arguments": json.dumps({
                    "draft": (
                        "Using the above customer review, operator notes, "
                        "and these additional facts, write a final reply (≤ 250 words). "
                        "Prefix any inferred detail with ASSUMPTION:. "
                        "At the end, include exactly this signature: "
                        f"{st.session_state.signature.strip() or '(No signature provided)'}"
                    )
                })
            }
            msgs.append({
                "role": "assistant",
                "content": None,
                "function_call": compose_call
            })

            try:
                msg2 = log_run_llm(
                    msgs,
                    api_key,
                    functions=FUNCTIONS,
                    function_call="compose_reply"
                )
            except Exception as e:
                st.error(f"❌ OpenAI API error: {e}")
                st.stop()

            if getattr(msg2, "function_call", None) and msg2.function_call.name == "compose_reply":
                st.session_state.draft = msg2.function_call.arguments.get("draft", "").strip()
            else:
                st.session_state.draft = (msg2.content or "").strip()

            st.session_state.stage = "done"
            st.experimental_rerun()


# ───────────────────────────────────────────────────────────────────────
# [2] Draft review loop (only return the corrected draft, no commentary)
# ───────────────────────────────────────────────────────────────────────
if st.session_state.stage == "done" and not st.session_state.reviewed_draft:
    review_prompt = (
        "You are a strict reviewer.\n"
        "TASK:\n"
        "- Audit the draft for factual accuracy, tone, and unauthorized promises.\n"
        "- Correct any issues directly in-line.\n"
        "- Delete or rewrite ASSUMPTION lines only if they are unsupported or unclear.\n"
        "- Keep total length no more than 250 words.\n"
        "**Output only the final, corrected draft** (no explanations)."
    )
    review_msgs = [
        {"role": "system", "content": review_prompt},
        {"role": "user", "content": st.session_state.draft or ""}
    ]
    try:
        review_msg = log_run_llm(review_msgs, api_key)
    except Exception as e:
        st.error(f"❌ OpenAI API error: {e}")
        st.stop()

    st.session_state.reviewed_draft = (review_msg.content or "").strip()
    st.session_state.stage = "reviewed"


# ───────────────────────────────────────────────────────────────────────
# [3] Display reviewed draft + regenerate/start-over + download + word count
# ───────────────────────────────────────────────────────────────────────
if st.session_state.reviewed_draft:
    st.header("Reviewed Draft Response")
    st.text_area(
        "Final draft after review",
        key="draft_edit",
        value=st.session_state.reviewed_draft,
        height=220
    )

    # Word‐count indicator
    wc = len(st.session_state.reviewed_draft.split())
    st.caption(f"Word count: {wc} / 250")
    if wc > 250:
        st.warning("⚠️ Draft exceeds 250 words. Consider regenerating or trimming.")

    # (4) Regenerate / Start over controls
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🔄 Regenerate draft", key="btn_regenerate"):
            for k in ["draft", "reviewed_draft", "translation", "reviewed_translation"]:
                st.session_state[k] = ""
            st.session_state.stage = "init"
            st.experimental_rerun()
    with col2:
        if st.button("🔄 Start over completely", key="btn_reset_all"):
            for k in [
                "stage", "questions", "answers", "draft", "reviewed_draft",
                "translation", "reviewed_translation", "operator_notes",
                "signature", "messages", "api_log"
            ]:
                if isinstance(st.session_state.get(k), str):
                    st.session_state[k] = ""
                else:
                    st.session_state[k] = [] if isinstance(st.session_state[k], list) else {}
            st.session_state.mode = "Simple"
            st.experimental_rerun()

    # (5) Download final reply
    st.download_button(
        label="📥 Download final reply",
        data=st.session_state.reviewed_draft,
        file_name="empathos_reply.txt",
        mime="text/plain"
    )

    st.markdown("---")

    # ───────────────────────────────────────────────────────────────────────
    # Translation controls (always visible if there's a reviewed draft)
    # ───────────────────────────────────────────────────────────────────────
    tgt = st.selectbox(
        "Translate final reply to:",
        LANGUAGE_OPTIONS,
        index=0,
        key="translation_language"
    )
    if st.button("Translate & review", key="btn_translate"):
        trans_prompt = (
            "You are a translation assistant. Translate the following reply into "
            f"{tgt} using professional unit-linked insurance terminology; ensure it sounds natural for native speakers with a background in unit-linked insurance.\n"
            "Do not add commentary or promises.\n"
            f"{st.session_state.reviewed_draft}"
        )
        msgs_trans = [
            {"role": "system", "content": trans_prompt}
        ]
        try:
            msg_trans = log_run_llm(msgs_trans, api_key)
        except Exception as e:
            st.error(f"❌ OpenAI API error (translation): {e}")
            st.stop()

        st.session_state.translation = (msg_trans.content or "").strip()
        st.session_state.stage = "translated"

    # If a raw translation exists but hasn't been reviewed yet
    if st.session_state.translation and not st.session_state.reviewed_translation:
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
        try:
            rev_msg = log_run_llm(rev_msgs, api_key)
        except Exception as e:
            st.error(f"❌ OpenAI API error: {e}")
            st.stop()

        st.session_state.reviewed_translation = (rev_msg.content or "").strip()
        st.session_state.stage = "reviewed_translation"

    # If a reviewed translation exists, show it
    if st.session_state.reviewed_translation:
        st.header("Final Translated Response")
        st.text_area(
            "Final translation after review",
            key="translated_output",
            value=st.session_state.reviewed_translation,
            height=220
        )

        wc_t = len(st.session_state.reviewed_translation.split())
        st.caption(f"Word count: {wc_t} / 250")
        if wc_t > 250:
            st.warning("⚠️ Translated reply exceeds 250 words.")

        st.download_button(
            label="📥 Download translated reply",
            data=st.session_state.reviewed_translation,
            file_name="empathos_reply_translated.txt",
            mime="text/plain"
        )

# ----------------------------------------------------------------------
# Debug: show full API log at bottom (collapsed by default)
# ----------------------------------------------------------------------
if st.session_state.api_log:
    if st.checkbox("🔍 Show API Communication Log", key="show_api_log"):
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
