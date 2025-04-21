# Empathos – v3.1 (23 Apr 2025)  — refreshed labels + operator Q‑A loop
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
# Helper functions
# ----------------------------------------------------------------------
def info(label, val, tip):
    st.text_input(label, value=val, disabled=True, help=tip, label_visibility="visible")


def desired():
    tone = st.session_state.tone_choice if st.session_state.mode == "Advanced" else "Neutral"
    form = st.session_state.formality_choice if st.session_state.mode == "Advanced" else st.session_state.formality
    length = st.session_state.length_choice if st.session_state.mode == "Advanced" else st.session_state.length_label
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
    return chat("Label sentiment as 'Very negative', 'Negative', 'Neutral', 'Positive', or 'Very positive'. Return only the label.", t, k)


def detect_formality(t, k):
    return chat("Classify formality as 'Casual', 'Neutral', or 'Formal'. Return only the label.", t, k)


def classify_slant(t, k):
    return chat("Classify complaint as 'Failure‑focused', 'Loss‑focused', or 'Neutral'. Return only the label.", t, k)


def detect_language(t, k):
    return chat("Detect the language of the following text. Return only the language name in English.", t, k, model="gpt-4.1-mini")

# ----------------------------------------------------------------------
# Session‑state defaults
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
        st.session_state.setdefault(k, v)

init()

# ----------------------------------------------------------------------
# Mode & input fields
# ----------------------------------------------------------------------
st.radio("Interface mode", ["Simple", "Advanced"], key="mode", horizontal=True)

client_review = st.text_area(
    "Customer message or review",
    placeholder="Paste the customer's text here",
    height=140
)

st.text_area(
    "Additional information for answer (operator notes)",
    key="operator_notes",
    placeholder="Reply to open questions or add facts the model needs.",
    height=100
)

st.radio(
    "Response channel",
    ["Email (private)", "Public post"],
    key="channel_type",
    horizontal=True
)

api_key = st.text_input("OpenAI API key", type="password")

# ----------------------------------------------------------------------
# Generate draft
# ----------------------------------------------------------------------
if st.button("Generate response draft", type="primary"):
    if not client_review.strip() or not api_key:
        st.error("Please provide the customer text and an API key.")
    else:
        # ------------ automatic analysis --------------------------------
        st.session_state.sentiment = analyze_sentiment(client_review, api_key)
        st.session_state.formality = detect_formality(client_review, api_key)
        st.session_state.slant     = classify_slant(client_review, api_key)
        st.session_state.lang      = detect_language(client_review, api_key)
        wc = len(client_review.split())
        st.session_state.length_label = next(lbl for low, up, lbl in LENGTH_CATEGORIES if low <= wc <= up)

        tone, formality, length = desired()
        channel_phrase = "private email" if "Email" in st.session_state.channel_type else "public response"

        # ------------ system prompt -------------------------------------
                # ------------ system prompt -------------------------------------
        system_prompt = f"""
### 0 ▸ Operator notes (provided by human)
{st.session_state.operator_notes or 'None'}

### 1 ▸ Operator follow‑up questions
• If you still need information from the operator, write each prompt on its own
  line starting with **?**.  
• If the notes above answer everything, DO NOT output any ?‑lines.

### 2 ▸ Craft the customer reply
Write the full response **after** any ?‑lines (or immediately if none) in
**{channel_phrase}** style.

#### Context signals to respect
• Sentiment …… {st.session_state.sentiment}  
• Formality ……… {formality}  
• Complaint slant … {st.session_state.slant}  
• Desired length … {length}  
• Desired tone …… {tone}

#### Writing guidelines
1. Open with empathy; acknowledge the customer’s feeling.  
2. Restate the core issue in one clear sentence.  
3. If slant is *Failure‑focused*, emphasise sincere apology and ownership.  
4. If slant is *Loss‑focused*, emphasise remedy, compensation or next steps.  
5. Use precise life‑insurance terminology, avoid jargon the customer wouldn’t know.  
6. Keep personal data private; no policy numbers or amounts in public replies.  
7. Private replies may be detailed; public replies must be concise and
   free of sensitive info.  
8. End with a clear action or invitation (e.g. “Please email us at…”, “We’ll
   call you by…”, “Let us know if…”).  
9. Maintain professional yet warm tone — neither robotic nor overly familiar.  
10. Do **not** include any lines that start with “?” in the customer reply.
""".strip()


        client = OpenAI(api_key=api_key)
        res = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",
                 "content": f"Customer review:\n{client_review}\n\nOperator notes:\n{st.session_state.operator_notes or '-'}"}
            ],
            max_tokens=650,
            temperature=0.9
        )

        draft_lines, followup_lines = [], []
        for raw in res.choices[0].message.content.splitlines():
            ln = raw.lstrip()
            if ln.startswith("?"):
                cleaned = re.sub(r"^[\?\s\-–—]+", "", ln).strip()
                if cleaned:
                    followup_lines.append(cleaned)
            else:
                draft_lines.append(raw)

        st.session_state.followups   = followup_lines
        st.session_state.draft       = "\n".join(draft_lines).strip()
        st.session_state.translation = ""   # clear any previous translation

# ----------------------------------------------------------------------
# Display sections
# ----------------------------------------------------------------------
if st.session_state.draft:
    tone, formality, length = desired()

    # ---------- Analysis summary & parameters ---------------------------
    if st.session_state.mode == "Simple":
        col_sum, col_par = st.columns([3, 2])
        with col_sum:
            st.subheader("Analysis summary")
            info("Sentiment", st.session_state.sentiment, "Detected emotional tone.")
            info("Formality (detected)", st.session_state.formality, "How casual or formal the customer wrote.")
            info("Complaint slant", st.session_state.slant, "Focus on failure, loss, or neutral.")
            info("Message length (detected)", st.session_state.length_label, "Size of original message.")
            info("Detected language", st.session_state.lang, "Language of customer text.")
        with col_par:
            st.subheader("Parameters applied")
            info("Tone", tone, "Tone used or selected.")
            info("Formality (reply)", formality, "Formality used in reply.")
            info("Reply length", length, "Target length.")
    else:
        st.subheader("Analysis summary")
        info("Sentiment", st.session_state.sentiment, "Detected emotional tone.")
        info("Formality (detected)", st.session_state.formality, "How casual or formal the customer wrote.")
        info("Complaint slant", st.session_state.slant, "Focus on failure, loss, or neutral.")
        info("Message length (detected)", st.session_state.length_label, "Size of original message.")
        info("Detected language", st.session_state.lang, "Language of customer text.")
        st.markdown("#### Adjust parameters")
        st.select_slider("Tone", TONE_OPTIONS, key="tone_choice")
        st.select_slider("Reply length", LENGTH_OPTIONS, key="length_choice")
        st.select_slider("Formality level", FORMALITY_OPTIONS, key="formality_choice")
        st.markdown("---")

    # ---------- Draft ---------------------------------------------------
    st.header("Draft response")
    st.text_area("Editable draft response", key="draft_edit",
                 value=st.session_state.draft, height=220)

    # ---------- Follow‑up questions ------------------------------------
    st.markdown("### Open questions for operator")
    if st.session_state.followups:
        st.text_area(
            label="Questions (read‑only)",
            value="\n".join(st.session_state.followups),
            height=110,
            disabled=True,
            key="followups_view"
        )
    else:
        st.info("No open questions – ready to send.")

    # ---------- Translation --------------------------------------------
    default_lang = st.session_state.lang if st.session_state.lang in LANGUAGE_OPTIONS else "English"
    target_lang = st.selectbox("Translate final reply to:", LANGUAGE_OPTIONS,
                               index=LANGUAGE_OPTIONS.index(default_lang))

    if st.button("Translate & update"):
        translation_prompt = f"Translate the reply into {target_lang} using accurate insurance terminology while keeping tone and meaning."
        trans = chat(translation_prompt, st.session_state.draft, api_key,
                     model="gpt-4.1-mini", max_tokens=1000)
        st.session_state.translation = trans

# ----------------------------------------------------------------------
# Translation display
# ----------------------------------------------------------------------
if st.session_state.translation:
    st.header("Translated response")
    st.text_area("Final translation of reply", key="translated_output",
                 value=st.session_state.translation, height=220)
