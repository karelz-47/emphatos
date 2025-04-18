"""
Empathos – Streamlit app with manual analysis trigger
Features:
1. Manual "Analyze Review" button for sentiment, length, formality detection.
2. Display of detected vs. suggested parameters (words only).
3. Text‐only select_sliders for Tone, Length, Formality.
4. Follow‑up questions aimed at the operator when requests are unprocessed.
"""

import json
import streamlit as st
from openai import OpenAI

# ------------------------------------------------------------
# Helper functions and caching
# ------------------------------------------------------------
@st.cache_data(ttl=3600)
def analyze_sentiment(text: str, api_key: str) -> float:
    """Returns a float between -1 and +1 representing sentiment."""
    try:
        client = OpenAI(api_key=api_key)
        messages = [
            {"role": "system", "content": "Return one number between -1 and 1 for sentiment."},
            {"role": "user", "content": text},
        ]
        res = client.chat.completions.create(
            model="gpt-4.1-mini", messages=messages, max_tokens=3, temperature=0
        )
        return float(res.choices[0].message.content.strip())
    except Exception:
        return 0.0

@st.cache_data(ttl=3600)
def detect_formality(text: str, api_key: str) -> str:
    """Returns 'casual', 'neutral', or 'formal'."""
    try:
        client = OpenAI(api_key=api_key)
        messages = [
            {"role": "system", "content": "Label the style as 'casual', 'neutral', or 'formal'."},
            {"role": "user", "content": text},
        ]
        res = client.chat.completions.create(
            model="gpt-4.1-mini", messages=messages, max_tokens=3, temperature=0
        )
        return res.choices[0].message.content.lower().strip()
    except Exception:
        return "neutral"

# ------------------------------------------------------------
# Option lists
# ------------------------------------------------------------
TONE_OPTIONS = ["Very Apologetic", "Apologetic", "Neutral", "Enthusiastic", "Very Enthusiastic"]
LENGTH_OPTIONS = ["Very Concise", "Concise", "Balanced", "Detailed", "Very Detailed"]
FORMALITY_OPTIONS = ["Very Casual", "Casual", "Professional", "Formal", "Very Formal"]

# Map sentiment label to suggested tone
SENT_LABEL_MAP = {
    "Very negative": "Very Apologetic",
    "Negative": "Apologetic",
    "Neutral": "Neutral",
    "Positive": "Enthusiastic",
    "Very positive": "Very Enthusiastic",
}

# ------------------------------------------------------------
# Session state initialization
# ------------------------------------------------------------
state_keys = [
    'draft_response', 'follow_up_questions', 'final_response',
    'det_sentiment', 'det_label', 'det_length', 'det_formality',
    'sugg_tone', 'sugg_length', 'sugg_formality', 'analyzed',
    'tone_choice', 'length_choice', 'formality_choice'
]
for k in state_keys:
    if k not in st.session_state:
        st.session_state[k] = False if k == 'analyzed' else ""

# ------------------------------------------------------------
# Page config
# ------------------------------------------------------------
st.set_page_config(page_title="Empathos", layout="centered")
st.title("Empathos")
st.subheader("Your Voice, Their Peace of Mind")

# ------------------------------------------------------------
# 1. User inputs
# ------------------------------------------------------------
client_review = st.text_area(
    "Policyholder’s Review or Comment",
    placeholder="Enter the policyholder’s feedback…",
    key="client_review",
    height=140,
)
insights = st.text_input(
    "Additional Context (optional)",
    placeholder="E.g. policy number, advisor name…",
    key="insights",
)
api_key = st.text_input(
    "OpenAI API Key",
    type="password",
    placeholder="sk-…",
    key="api_key",
)

# ------------------------------------------------------------
# 2. Analysis trigger
# ------------------------------------------------------------
if st.button("Analyze Review"):
    if not client_review.strip():
        st.error("Please enter a policyholder review to analyze.")
    elif not api_key:
        st.error("Please enter your OpenAI API key.")
    else:
        # Sentiment
        polarity = analyze_sentiment(client_review, api_key)
        st.session_state.det_sentiment = polarity
        # label
        if polarity <= -0.75:
            lbl = "Very negative"
        elif polarity <= -0.25:
            lbl = "Negative"
        elif polarity < 0.25:
            lbl = "Neutral"
        elif polarity < 0.75:
            lbl = "Positive"
        else:
            lbl = "Very positive"
        st.session_state.det_label = lbl
        # suggested tone
        st.session_state.sugg_tone = SENT_LABEL_MAP.get(lbl, "Neutral")

        # Length detection
        count = len(client_review.split())
        st.session_state.det_length = f"{count} words"
        # bucket
        if count < 20:
            st.session_state.sugg_length = LENGTH_OPTIONS[0]
        elif count < 50:
            st.session_state.sugg_length = LENGTH_OPTIONS[1]
        elif count < 100:
            st.session_state.sugg_length = LENGTH_OPTIONS[2]
        elif count < 200:
            st.session_state.sugg_length = LENGTH_OPTIONS[3]
        else:
            st.session_state.sugg_length = LENGTH_OPTIONS[4]

        # Formality detection
        form = detect_formality(client_review, api_key)
        st.session_state.det_formality = form.title()
        if form == "casual":
            st.session_state.sugg_formality = FORMALITY_OPTIONS[1]
        elif form == "neutral":
            st.session_state.sugg_formality = FORMALITY_OPTIONS[2]
        else:
            st.session_state.sugg_formality = FORMALITY_OPTIONS[3]

        # defaults for selectors
        st.session_state.tone_choice = st.session_state.sugg_tone
        st.session_state.length_choice = st.session_state.sugg_length
        st.session_state.formality_choice = st.session_state.sugg_formality
        st.session_state.analyzed = True

# ------------------------------------------------------------
# 3. Display Analysis & selectors
# ------------------------------------------------------------
if st.session_state.analyzed:
    st.markdown("### Analysis Results")
    st.write(f"Detected sentiment: {st.session_state.det_sentiment:+.2f} ({st.session_state.det_label})")
    st.write(f"Suggested tone: {st.session_state.sugg_tone}")
    st.write(f"Detected length: {st.session_state.det_length}")
    st.write(f"Suggested length: {st.session_state.sugg_length}")
    st.write(f"Detected formality: {st.session_state.det_formality}")
    st.write(f"Suggested formality: {st.session_state.sugg_formality}")

    tone_choice = st.select_slider(
        "Tone of reply", options=TONE_OPTIONS,
        value=st.session_state.tone_choice, key="tone_choice"
    )
    length_choice = st.select_slider(
        "Length of reply", options=LENGTH_OPTIONS,
        value=st.session_state.length_choice, key="length_choice"
    )
    formality_choice = st.select_slider(
        "Formality of reply", options=FORMALITY_OPTIONS,
        value=st.session_state.formality_choice, key="formality_choice"
    )

# ------------------------------------------------------------
# 4. Generate Draft
# ------------------------------------------------------------
if st.session_state.analyzed and st.button("Generate Draft"):
    if not api_key:
        st.error("Please enter your OpenAI API key.")
    else:
        sys_prompt = (
            "You are a customer-service specialist for unit-linked life insurance.\n"
            f"Write a reply that is {st.session_state.tone_choice.lower()}, {st.session_state.length_choice.lower()}, {st.session_state.formality_choice.lower()}.\n"
            "If the review indicates a request hasn’t been processed, prepend a line starting with '? ' asking the operator to confirm receipt, status, and expected completion time.\n"
            "• Thank the policyholder and restate only the issues mentioned.\n"
            "• Use correct life-insurance terms.\n"
            "• Offer a concrete next step or contact."
        )
        user_msg = f"Review: {client_review}\nContext: {insights or '-'}"
        client = OpenAI(api_key=api_key)
        res = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=300, temperature=0.9
        )
        raw = res.choices[0].message.content.strip()
        lines = raw.splitlines()
        draft = [l for l in lines if not l.startswith('?')]
        qlist = [l for l in lines if l.startswith('?')]
        st.session_state.draft_response = "\n".join(draft).strip()
        st.session_state.follow_up_questions = (
            "\n".join(f"• {q[1:].strip()}" for q in qlist)
            if qlist else "No follow-up questions."
        )

# ------------------------------------------------------------
# 5. Display Draft & Questions
# ------------------------------------------------------------
if st.session_state.draft_response:
    st.header("Draft Response")
    st.text_area(
        "Draft (editable)", value=st.session_state.draft_response,
        height=200, key="draft_editable", label_visibility="collapsed"
    )
    with st.expander("Follow‑up Questions"):
        st.write(st.session_state.follow_up_questions)

# ------------------------------------------------------------
# 6. Translation
# ------------------------------------------------------------
st.header("Translate Final Version")
final_language = st.selectbox(
    "Language of Final Version:",
    ["English","Slovak","Italian","Icelandic","Hungarian","German","Czech","Polish","Vulcan"],
    key="final_language"
)
if st.session_state.draft_response and st.button("Translate Final Version"):
    translator_sys = (
        f"You are a professional translator. Render the text into {final_language}, "
        "using clear, natural wording and the insurance terms typically used in that language."
    )
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": translator_sys},
            {"role": "user", "content": st.session_state.draft_response}
        ],
        max_tokens=1000, temperature=0
    )
    st.session_state.final_response = resp.choices[0].message.content.strip()

# ------------------------------------------------------------
# 7. Display Translation
# ------------------------------------------------------------
if st.session_state.final_response:
    st.header("Final Response (Translated)")
    st.text_area(
        "Translation result", value=st.session_state.final_response,
        height=200, key="translation_area", label_visibility="collapsed"
    )
