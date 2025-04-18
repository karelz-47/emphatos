"""Empathos – Streamlined Streamlit Front‑End with Manual Analysis Trigger
Features:
1. Manual "Analyze Review" button for sentiment, length, formality detection.
2. Display of detected vs. suggested parameters (words only).
3. Select‑sliders for Tone, Length, Formality with text options.
4. Improved follow‑up questions aimed at the operator when requests are unprocessed.
"""

from __future__ import annotations
import json
import streamlit as st
from openai import OpenAI

# --------------------------------------------------------------
# Constants & mappings
# --------------------------------------------------------------
TONE_OPTIONS = ["Very Apologetic", "Apologetic", "Neutral", "Enthusiastic", "Very Enthusiastic"]
TONE_MAP = {opt: val for opt, val in zip(TONE_OPTIONS, [-5, -3, 0, 3, 5])}

LENGTH_OPTIONS = ["Very Concise", "Concise", "Balanced", "Detailed", "Very Detailed"]
LENGTH_MAP = {opt: val for opt, val in zip(LENGTH_OPTIONS, [-5, 0, 5, 8, 10])}
# (internal numeric not used except prompt variability)

FORMALITY_OPTIONS = ["Very Casual", "Casual", "Professional", "Formal", "Very Formal"]
FORMALITY_MAP = {opt: val for opt, val in zip(FORMALITY_OPTIONS, [-5, -3, 0, 3, 5])}

# --------------------------------------------------------------
# Session‐state initialization
# --------------------------------------------------------------
for key in ("draft_response", "follow_up_questions", "final_response",
            "det_sentiment", "det_length", "det_formality",
            "sugg_tone", "sugg_length", "sugg_formality",
            "analyzed"):
    st.session_state.setdefault(key, "" if key.startswith("det_") or key.startswith("sugg_") else False)

# --------------------------------------------------------------
# Page config and title
# --------------------------------------------------------------
st.set_page_config(page_title="Empathos", layout="centered")
st.title("Empathos")
st.subheader("Your Voice, Their Peace of Mind")

# --------------------------------------------------------------
# 1. User inputs
# --------------------------------------------------------------
client_review = st.text_area(
    label="Policyholder’s Review or Comment",
    placeholder="Enter the policyholder’s feedback…",
    key="client_review",
    height=140,
)
insights = st.text_input(
    label="Additional Context (optional)",
    placeholder="E.g. policy number, advisor name…",
    key="insights",
)
api_key = st.text_input(
    label="OpenAI API Key",
    type="password",
    placeholder="sk-…",
    key="api_key",
)

# --------------------------------------------------------------
# 2. Analysis trigger
# --------------------------------------------------------------
if st.button("Analyze Review"):
    if not client_review.strip():
        st.error("Please enter a policyholder review to analyze.")
    elif not api_key:
        st.error("Please enter your OpenAI API key.")
    else:
        # Sentiment
        @st.cache_data(ttl=3600)
        def analyze_sentiment(text: str) -> float:
            client = OpenAI(api_key=api_key)
            msgs = [
                {"role": "system", "content": "Return one number between -1 and 1 for sentiment."},
                {"role": "user", "content": text},
            ]
            res = client.chat.completions.create(model="gpt-4.1-mini", messages=msgs, max_tokens=3)
            try:
                return float(res.choices[0].message.content.strip())
            except:
                return 0.0

        polarity = analyze_sentiment(client_review)
        st.session_state.det_sentiment = polarity
        # map to label
        if polarity <= -0.75:
            label = "Very negative"
        elif polarity <= -0.25:
            label = "Negative"
        elif polarity < 0.25:
            label = "Neutral"
        elif polarity < 0.75:
            label = "Positive"
        else:
            label = "Very positive"
        st.session_state.sugg_tone = TONE_OPTIONS[2] if label == "Neutral" else (
            TONE_OPTIONS[0] if label == "Very negative" else
            TONE_OPTIONS[1] if label == "Negative" else
            TONE_OPTIONS[3] if label == "Positive" else
            TONE_OPTIONS[4]
        )

        # Length detection
        count = len(client_review.split())
        st.session_state.det_length = f"{count} words"
        # simple buckets
        st.session_state.sugg_length = (
            LENGTH_OPTIONS[0] if count < 20 else
            LENGTH_OPTIONS[1] if count < 50 else
            LENGTH_OPTIONS[2] if count < 100 else
            LENGTH_OPTIONS[3] if count < 200 else
            LENGTH_OPTIONS[4]
        )

        # Formality detection
        @st.cache_data(ttl=3600)
        def detect_formality(text: str) -> str:
            client = OpenAI(api_key=api_key)
            msgs = [
                {"role": "system", "content": "Label style as 'casual', 'neutral', or 'formal'."},
                {"role": "user", "content": text},
            ]
            res = client.chat.completions.create(model="gpt-4.1-mini", messages=msgs, max_tokens=3)
            return res.choices[0].message.content.lower().strip()

        form = detect_formality(client_review)
        st.session_state.det_formality = form.title()
        st.session_state.sugg_formality = (
            FORMALITY_OPTIONS[0] if form == "casual" else
            FORMALITY_OPTIONS[2] if form == "neutral" else
            FORMALITY_OPTIONS[3]
        )
        st.session_state.analyzed = True

# --------------------------------------------------------------
# 3. Show detected vs suggested
# --------------------------------------------------------------
if st.session_state.analyzed:
    st.markdown(f"**Detected sentiment:** {st.session_state.det_sentiment:+.2f} ({label})")
    st.markdown(f"**Suggested tone:** {st.session_state.sugg_tone}")
    st.markdown(f"**Detected length:** {st.session_state.det_length}")
    st.markdown(f"**Suggested length:** {st.session_state.sugg_length}")
    st.markdown(f"**Detected formality:** {st.session_state.det_formality}")
    st.markdown(f"**Suggested formality:** {st.session_state.sugg_formality}")

    # 4. Sliders (text select)
    tone_choice = st.select_slider(
        "Tone of reply", options=TONE_OPTIONS, value=st.session_state.sugg_tone
    )
    length_choice = st.select_slider(
        "Length of reply", options=LENGTH_OPTIONS, value=st.session_state.sugg_length
    )
    formality_choice = st.select_slider(
        "Formality of reply", options=FORMALITY_OPTIONS, value=st.session_state.sugg_formality
    )

# --------------------------------------------------------------
# 5. Generate draft
# --------------------------------------------------------------
def generate_draft() -> None:
    tone_val = TONE_MAP.get(tone_choice, 0)
    length_val = LENGTH_MAP.get(length_choice, 0)
    form_val = FORMALITY_MAP.get(formality_choice, 0)
    # compose system prompt
    sys = (
        "You are a customer-service specialist for unit-linked life insurance.\n"
        f"Write a reply that is {tone_choice.lower()}, {length_choice.lower()}, and {formality_choice.lower()}.\n"
        "If the review indicates a request hasn’t been processed, ask the operator to confirm receipt of that request, its current status, and expected completion time.\n"
        "• Thank the policy-holder and restate only the issues mentioned.\n"
        "• Explain using correct life-insurance terms.\n"
        "• Offer a concrete next step or contact.\n"
    )
    user = f"Review: {client_review}\nAdditional context: {insights or '—'}"
    client = OpenAI(api_key=api_key)
    res = client.chat.completions.create(
        model="gpt-4.1", messages=[{"role":"system","content":sys},{"role":"user","content":user}],
        max_tokens=300, temperature=0.9
    )
    out = res.choices[0].message.content.strip()
    # parse follow-ups: any lines starting with '?'
    lines = out.splitlines()
    draft_lines = [l for l in lines if not l.startswith('?')]
    qs = [l for l in lines if l.startswith('?')]
    st.session_state.draft_response = "\n".join(draft_lines).strip()
    if qs:
        st.session_state.follow_up_questions = "\n".join(f"• {l[1:].strip()}" for l in qs)
    else:
        st.session_state.follow_up_questions = "No follow-up questions."

if st.button("Generate Draft") and st.session_state.analyzed:
    if not api_key:
        st.error("API key missing.")
    else:
        generate_draft()

# --------------------------------------------------------------
# 6. Display draft & questions
# --------------------------------------------------------------
if st.session_state.draft_response:
    st.header("Draft Response")
    st.text_area(
    "Translation",
    value=st.session_state.final_response,
    height=200,
    key="translation_area",
    label_visibility="collapsed",
)
    with st.expander("Follow‑up Questions"):
        st.write(st.session_state.follow_up_questions)

# --------------------------------------------------------------
# 7. Translation
# --------------------------------------------------------------
st.header("Translate Final Version")
final_language = st.selectbox("Language of Final Version:", [
    "English","Slovak","Italian","Icelandic","Hungarian","German","Czech","Polish","Vulcan"
])
if st.button("Translate Final Version") and st.session_state.draft_response:
    translator_sys = (
        f"You are a professional translator. Render the text into {final_language}, "
        "using clear, natural wording and the insurance terms typically used in that language."
    )
    client = OpenAI(api_key=api_key)
    res = client.chat.completions.create(
        model="gpt-4.1-mini", messages=[
            {"role":"system","content":translator_sys},
            {"role":"user","content":st.session_state.draft_response}
        ], max_tokens=1000, temperature=0
    )
    st.session_state.final_response = res.choices[0].message.content.strip()

# --------------------------------------------------------------
# 8. Display final translation
# --------------------------------------------------------------
if st.session_state.final_response:
    st.header("Final Response (Translated)")
    st.text_area("Translation", value=st.session_state.final_response, height=200)
