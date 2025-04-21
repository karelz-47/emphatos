# Empathos – v3 (23 Apr 2025)  — operator Q‑A loop
# ----------------------------------------------------------------------
import re
import streamlit as st
from openai import OpenAI

# ----------------------------------------------------------------------
# Page config
# ----------------------------------------------------------------------
st.set_page_config(page_title="Empathos", layout="centered")
st.title("Empathos")
st.subheader("Your voice, their peace of mind")

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
LANGUAGE_OPTIONS = [
    "English", "Slovak", "Italian", "Icelandic",
    "Hungarian", "German", "Czech", "Polish", "Vulcan"
]

LENGTH_CATEGORIES = [
    (0, 20, "Very concise"), (21, 50, "Concise"),
    (51, 100, "Balanced"), (101, 200, "Detailed"),
    (201, 9_999, "Very detailed")
]

TONE_OPTIONS      = ["Very apologetic", "Apologetic", "Neutral",
                     "Enthusiastic", "Very enthusiastic"]
FORMALITY_OPTIONS = ["Very casual", "Casual", "Neutral",
                     "Professional", "Very formal"]
LENGTH_OPTIONS    = ["Very concise", "Concise", "Balanced",
                     "Detailed", "Very detailed"]

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def info(label, val, tip):
    st.text_input(label, value=val, disabled=True, help=tip)


def desired():
    tone = (st.session_state.tone_choice
            if st.session_state.mode == "Advanced" else "Neutral")
    form = (st.session_state.formality_choice
            if st.session_state.mode == "Advanced"
            else st.session_state.formality)
    length = (st.session_state.length_choice
              if st.session_state.mode == "Advanced"
              else st.session_state.length_label)
    return tone, form, length


def chat(prompt, user, key, model="gpt-4.1", max_tokens=10, temp=0):
    client = OpenAI(api_key=key)
    out = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": prompt},
                  {"role": "user", "content": user}],
        max_tokens=max_tokens,
        temperature=temp
    )
    return out.choices[0].message.content.strip()


def analyze_sentiment(t, k):
    return chat("Label sentiment as 'Very negative', 'Negative', 'Neutral', "
                "'Positive', or 'Very positive'. Return only the label.", t, k)


def detect_formality(t, k):
    return chat("Classify formality as 'Casual', 'Neutral', or 'Formal'. "
                "Return only the label.", t, k)


def classify_slant(t, k):
    return chat("Classify complaint as 'Failure‑focused', 'Loss‑focused', "
                "or 'Neutral'. Return only the label.", t, k)


def detect_language(t, k):
    return chat("Detect the language of the following text. "
                "Return only the language name in English.", t, k,
                model="gpt-4.1-mini")

# ----------------------------------------------------------------------
# Session defaults
# ----------------------------------------------------------------------
def init():
    defaults = {
        "sentiment": "", "formality": "", "slant": "", "lang": "",
        "length_label": "",
        "tone_choice": "Neutral", "formality_choice": "Professional",
        "length_choice": "Balanced",
        "draft": "", "followups": [], "translation": "", "mode": "Simple",
        "operator_notes": ""
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init()

# ----------------------------------------------------------------------
# Mode & inputs
# ----------------------------------------------------------------------
st.radio("Mode", ["Simple", "Advanced"], key="mode", horizontal=True)

client_review = st.text_area(
    "Customer review",
    placeholder="Paste the customer's message or review here",
    height=140
)

st.text_area(
    "Additional information for answer (operator notes)",
    key="operator_notes",
    placeholder="Reply to follow‑up questions here, add any facts the model needs.",
    height=100
)

st.radio("Channel", ["Email (private)", "Public post"],
         key="channel_type", horizontal=True)

api_key = st.text_input("OpenAI API key", type="password")

# ----------------------------------------------------------------------
# Generate draft
# ----------------------------------------------------------------------
if st.button("Generate draft", type="primary"):
    if not client_review.strip() or not api_key:
        st.error("Please fill in the review and API key.")
    else:
        # ---------- analysis -------------------------------------------
        st.session_state.sentiment = analyze_sentiment(client_review, api_key)
        st.session_state.formality = detect_formality(client_review, api_key)
        st.session_state.slant     = classify_slant(client_review, api_key)
        st.session_state.lang      = detect_language(client_review, api_key)
        wc = len(client_review.split())
        st.session_state.length_label = next(
            lbl for low, up, lbl in LENGTH_CATEGORIES if low <= wc <= up
        )

        tone, formality, length = desired()
        channel_phrase = "private email" if "Email" in st.session_state.channel_type else "public response"

        # ---------- system prompt --------------------------------------
        system_prompt = f"""
### 0. Operator notes (provided by human)
{st.session_state.operator_notes or 'None'}

### 1. Operator follow‑up questions
If you still need operator input, write each prompt on its own line starting
with **?**. If the notes answer everything, DO NOT output any ?‑lines.

### 2. Customer reply
After the ?‑lines (if any), write the full reply in {channel_phrase} style.

Signals:
• Sentiment: {st.session_state.sentiment}
• Formality: {formality}
• Complaint slant: {st.session_state.slant}
• Desired length: {length}
• Desired tone: {tone}
""".strip()

        client = OpenAI(api_key=api_key)
        res = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",
                 "content": f"Review: {client_review}\nNotes: {st.session_state.operator_notes or '-'}"}
            ],
            max_tokens=650,
            temperature=0.9
        )

        # ---------- split ?‑lines / draft ------------------------------
        draft_lines, followup_lines = [], []
        for raw in res.choices[0].message.content.splitlines():
            ln = raw.lstrip()
            if ln.startswith("?"):
                cleaned = re.sub(r"^[\?\s\-–—]+", "", ln).strip()
                if cleaned:
                    followup_lines.append(cleaned)
            else:
                draft_lines.append(raw)

        st.session_state.followups = followup_lines
        st.session_state.draft     = "\n".join(draft_lines).strip()
        st.session_state.translation = ""   # clear old translation

# ----------------------------------------------------------------------
# Display
# ----------------------------------------------------------------------
if st.session_state.draft:
    tone, formality, length = desired()

    # ---------- summary / parameters ----------------------------------
    if st.session_state.mode == "Simple":
        col_sum, col_par = st.columns([3, 2])
        with col_sum:
            st.subheader("Analysis summary")
            info("Sentiment", st.session_state.sentiment,
                 "Overall emotional tone.")
            info("Formality (detected)", st.session_state.formality,
                 "Casual vs. formal.")
            info("Complaint slant", st.session_state.slant,
                 "Focus on failure, loss, or neutral.")
            info("Length (detected)", st.session_state.length_label,
                 "Size of the customer's message.")
            info("Language", st.session_state.lang,
                 "Detected language.")
        with col_par:
            st.subheader("Parameters used")
            info("Tone", tone, "Chosen or default.")
            info("Formality (reply)", formality, "Reply formality.")
            info("Length", length, "Reply length.")
    else:
        st.subheader("Analysis summary")
        info("Sentiment", st.session_state.sentiment, "Overall emotional tone.")
        info("Formality (detected)", st.session_state.formality, "Casual vs. formal.")
        info("Complaint slant", st.session_state.slant, "Failure / loss / neutral.")
        info("Length (detected)", st.session_state.length_label, "Size of message.")
        info("Language", st.session_state.lang, "Detected language.")
        st.markdown("#### Override parameters")
        st.select_slider("Desired tone", TONE_OPTIONS, key="tone_choice")
        st.select_slider("Reply length", LENGTH_OPTIONS, key="length_choice")
        st.select_slider("Formality level", FORMALITY_OPTIONS, key="formality_choice")
        st.markdown("---")

    # ---------- draft --------------------------------------------------
    st.header("Draft response")
    st.text_area("Editable draft", key="draft_edit",
                 value=st.session_state.draft, height=220)

    # ---------- follow‑ups --------------------------------------------
    st.markdown("### Operator follow‑up questions")
    if st.session_state.followups:
        st.text_area("Questions (read‑only)",
                     value="\n".join(st.session_state.followups),
                     height=110, disabled=True, key="followups_view")
    else:
        st.info("No operator follow‑up questions for this message.")

    # ---------- translation -------------------------------------------
    default_lang = (st.session_state.lang if st.session_state.lang in LANGUAGE_OPTIONS else "English")
    target_lang = st.selectbox("Translate to:", LANGUAGE_OPTIONS,
                               index=LANGUAGE_OPTIONS.index(default_lang))

    if st.button("Translate & update"):
        translation_prompt = (f"Translate the reply into {target_lang} using accurate "
                              f"insurance terminology while keeping tone and meaning.")
        trans = chat(translation_prompt, st.session_state.draft,
                     api_key, model="gpt-4.1-mini", max_tokens=1000)
        st.session_state.translation = trans

# ----------------------------------------------------------------------
# Translation display
# ----------------------------------------------------------------------
if st.session_state.translation:
    st.header("Translated response")
    st.text_area("Final translation", key="translated_output",
                 value=st.session_state.translation, height=220)
