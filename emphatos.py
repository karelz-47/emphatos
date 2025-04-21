# Empathos – v2 (22 Apr 2025)  — emphasised follow‑ups + always‑visible panel
# ---------------------------------------------------------------------------
import re
import streamlit as st
from openai import OpenAI

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Empathos", layout="centered")
st.title("Empathos")
st.subheader("Your voice, their peace of mind")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def info_field(label: str, value: str, tooltip: str) -> None:
    st.text_input(label, value=value, disabled=True, help=tooltip)


def get_desired():
    tone = (st.session_state.tone_choice
            if st.session_state.mode == "Advanced" else "Neutral")
    formality = (st.session_state.formality_choice
                 if st.session_state.mode == "Advanced"
                 else st.session_state.formality)
    length = (st.session_state.length_choice
              if st.session_state.mode == "Advanced"
              else st.session_state.length_label)
    return tone, formality, length


def openai_chat(prompt: str, user_text: str, api_key: str,
                model: str = "gpt-4.1", max_tokens: int = 10,
                temperature: float = 0) -> str:
    client = OpenAI(api_key=api_key)
    res = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": prompt},
                  {"role": "user", "content": user_text}],
        max_tokens=max_tokens,
        temperature=temperature
    )
    return res.choices[0].message.content.strip()


def analyze_sentiment(t, k):
    return openai_chat(
        "Label sentiment as 'Very negative', 'Negative', 'Neutral', "
        "'Positive', or 'Very positive'. Return only the label.",
        t, k)


def detect_formality(t, k):
    return openai_chat(
        "Classify formality as 'Casual', 'Neutral', or 'Formal'. "
        "Return only the label.",
        t, k)


def classify_slant(t, k):
    return openai_chat(
        "Classify complaint as 'Failure‑focused', 'Loss‑focused', or 'Neutral'. "
        "Return only the label.",
        t, k)


def detect_language(t, k):
    return openai_chat(
        "Detect the language of the following text. "
        "Return only the language name in English.",
        t, k, model="gpt-4.1-mini")

# ---------------------------------------------------------------------------
# Session‑state defaults
# ---------------------------------------------------------------------------
def init_session():
    defaults = {
        "sentiment": "", "formality": "", "slant": "", "lang": "",
        "length_label": "", "tone_choice": "Neutral",
        "formality_choice": "Professional", "length_choice": "Balanced",
        "draft": "", "followups": [], "raw_response": "", "translation": "",
        "mode": "Simple"
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

# ---------------------------------------------------------------------------
# Mode & basic inputs
# ---------------------------------------------------------------------------
st.radio("Mode", ["Simple", "Advanced"], key="mode", horizontal=True)

client_review = st.text_area(
    "Customer review",
    placeholder="Paste the customer's message or review here",
    height=140
)

insights = st.text_input(
    "Internal notes (optional)",
    placeholder="Anything that helps us answer accurately"
)

st.radio("Channel", ["Email (private)", "Public post"],
         key="channel_type", horizontal=True)

api_key = st.text_input("OpenAI API key", type="password")

# ---------------------------------------------------------------------------
# Generate draft
# ---------------------------------------------------------------------------
if st.button("Generate draft", type="primary"):
    if not client_review.strip() or not api_key:
        st.error("Please fill in the review and API key.")
    else:
        # ---------- auto analysis -------------------------------------------------
        st.session_state.sentiment = analyze_sentiment(client_review, api_key)
        st.session_state.formality = detect_formality(client_review, api_key)
        st.session_state.slant     = classify_slant(client_review, api_key)
        st.session_state.lang      = detect_language(client_review, api_key)
        wc = len(client_review.split())
        st.session_state.length_label = next(
            label for low, up, label in LENGTH_CATEGORIES if low <= wc <= up
        )

        tone, formality, length = get_desired()
        channel_phrase = "private email" if "Email" in st.session_state.channel_type else "public response"

        # ---------- UPDATED, follow‑up‑first system prompt ------------------------
        system_prompt = f"""
### 1. Decide on operator follow‑up questions  
*Before you write the customer‑facing reply, think whether the operator needs to provide or verify any information (policy numbers, premium amounts, dates, KYC steps, product features, legal wording, escalation approval, etc.).*  
• If **yes**, output each operator prompt on its own line starting with exactly **‘?’**.  
• If **no**, output nothing that starts with ‘?’.  

### 2. Write the reply to the customer  
After the ‘?’ lines (if any), write the full response in **{channel_phrase}** style.

Use these signals for the reply:  
• Detected sentiment: {st.session_state.sentiment}  
• Detected formality: {formality}  
• Complaint slant: {st.session_state.slant}  
• Desired length: {length}  
• Desired tone: {tone}  

Guidelines:  
- Be empathetic and professional.  
- Acknowledge the customer's emotion.  
- If slant is 'Failure‑focused', emphasise apology; if 'Loss‑focused', emphasise remedy.  
- Use clear insurance terminology.  
- Restate the core issue briefly and offer next steps.  
- Public replies: be concise, no sensitive info.  
- Private replies: be detailed and action‑oriented.
""".strip()

        # ---------- LLM call ------------------------------------------------------
        client = OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",
                 "content": f"Review: {client_review}\nContext: {insights or '-'}"}
            ],
            max_tokens=650,
            temperature=0.9
        )
        raw_response = completion.choices[0].message.content.strip()
        st.session_state.raw_response = raw_response

        # ---------- split into followups + draft ----------------------------------
        lines = raw_response.splitlines()
        draft_lines, followup_lines = [], []

        for raw in lines:
            ln = raw.lstrip()
            if ln.startswith("?"):
                cleaned = re.sub(r"^[\?\s\-–—]+", "", ln).strip()
                if cleaned:
                    followup_lines.append(cleaned)
            else:
                draft_lines.append(raw)

        st.session_state.followups = followup_lines
        st.session_state.draft     = "\n".join(draft_lines).strip()
        st.session_state.translation = ""   # reset previous translation

# ---------------------------------------------------------------------------
# Display analysis, parameters, draft
# ---------------------------------------------------------------------------
if st.session_state.draft:
    tone, formality, length = get_desired()

    # ---------- Summary & parameters -------------------------------------
    if st.session_state.mode == "Simple":
        col_sum, col_par = st.columns([3, 2])
        with col_sum:
            st.subheader("Analysis summary")
            info_field("Sentiment", st.session_state.sentiment,
                       "Overall emotional tone of the customer's message.")
            info_field("Formality (detected)", st.session_state.formality,
                       "Degree of casual vs. formal language.")
            info_field("Complaint slant", st.session_state.slant,
                       "Focus on failure, loss, or neutral view.")
            info_field("Length (detected)", st.session_state.length_label,
                       "Approximate size of the customer's message.")
            info_field("Language", st.session_state.lang,
                       "Detected language of the original text.")
        with col_par:
            st.subheader("Parameters used")
            info_field("Tone", tone, "Chosen automatically or by you.")
            info_field("Formality (reply)", formality, "Reply formality.")
            info_field("Length", length, "Reply length target.")
    else:  # Advanced
        st.subheader("Analysis summary")
        info_field("Sentiment", st.session_state.sentiment,
                   "Overall emotional tone of the customer's message.")
        info_field("Formality (detected)", st.session_state.formality,
                   "Degree of casual vs. formal language.")
        info_field("Complaint slant", st.session_state.slant,
                   "Focus on failure, loss, or neutral view.")
        info_field("Length (detected)", st.session_state.length_label,
                   "Approximate size of the customer's message.")
        info_field("Language", st.session_state.lang,
                   "Detected language of the original text.")

        st.markdown("#### Override parameters")
        st.select_slider("Desired tone", options=TONE_OPTIONS,
                         key="tone_choice",
                         help="Override the automatic tone, if you like.")
        st.select_slider("Reply length", options=LENGTH_OPTIONS,
                         key="length_choice",
                         help="How detailed should the answer be?")
        st.select_slider("Formality level", options=FORMALITY_OPTIONS,
                         key="formality_choice",
                         help="Choose how casual or formal the reply sounds.")
        st.markdown("---")

    # ---------- Draft response -------------------------------------------
    st.header("Draft response")
    st.text_area("Editable draft",
                 key="draft_edit",
                 value=st.session_state.draft,
                 height=220)

    # ---------- Follow‑up pane (always visible) --------------------------
    st.markdown("### Operator follow‑up (raw)")
    st.text_area(
        label="Full LLM output (temporary debug view)",
        value=st.session_state.raw_response,
        height=200,
        key="raw_view",
        disabled=True
    )

    # ---------- Translation ---------------------------------------------
    default_lang = (st.session_state.lang
                    if st.session_state.lang in LANGUAGE_OPTIONS else "English")
    target_lang = st.selectbox(
        "Translate to:", LANGUAGE_OPTIONS,
        index=LANGUAGE_OPTIONS.index(default_lang)
    )

    if st.button("Translate & update"):
        translation_prompt = (
            f"You are a translator. Translate the reply into {target_lang}, "
            f"using accurate insurance terminology. Maintain the tone and meaning."
        )
        translated_text = openai_chat(
            translation_prompt, st.session_state.draft, api_key,
            model="gpt-4.1-mini", max_tokens=1000
        )
        st.session_state.translation = translated_text

# ---------------------------------------------------------------------------
# Show translated answer
# ---------------------------------------------------------------------------
if st.session_state.translation:
    st.header("Translated response")
    st.text_area(
        "Final translation",
        key="translated_output",
        value=st.session_state.translation,
        height=220
    )
