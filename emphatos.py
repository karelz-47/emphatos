import streamlit as st
from openai import OpenAI

# ------------------------------------------------------------
# Page config
# ------------------------------------------------------------
st.set_page_config(page_title="Empathos", layout="centered")
st.title("Empathos")
st.subheader("Your Voice, Their Peace of Mind")

# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------
LANGUAGE_OPTIONS = ["English","Slovak","Italian","Icelandic","Hungarian","German","Czech","Polish","Vulcan"]
LENGTH_CATEGORIES = [(0, 20, "Very Concise"), (21, 50, "Concise"), (51, 100, "Balanced"), (101, 200, "Detailed"), (201, 9999, "Very Detailed")]
TONE_OPTIONS = ["Very Apologetic", "Apologetic", "Neutral", "Enthusiastic", "Very Enthusiastic"]
FORMALITY_OPTIONS = ["Very Casual", "Casual", "Neutral", "Professional", "Very Formal"]
LENGTH_OPTIONS = ["Very Concise", "Concise", "Balanced", "Detailed", "Very Detailed"]

# ------------------------------------------------------------
# Helper functions (non-cached due to unhashable OpenAI clients)
# ------------------------------------------------------------
def analyze_sentiment(text: str, api_key: str) -> str:
    client = OpenAI(api_key=api_key)
    prompt = """Label the sentiment of the following customer message as one of:
    'Very negative', 'Negative', 'Neutral', 'Positive', 'Very positive'.
    Return only the label."""
    res = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text}],
        max_tokens=5, temperature=0
    )
    return res.choices[0].message.content.strip()

def detect_formality(text: str, api_key: str) -> str:
    client = OpenAI(api_key=api_key)
    prompt = """Classify the formality of this message as 'Casual', 'Neutral', or 'Formal'."""
    res = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text}],
        max_tokens=5, temperature=0
    )
    return res.choices[0].message.content.strip()

def classify_slant(text: str, api_key: str) -> str:
    client = OpenAI(api_key=api_key)
    prompt = (
        "Analyze the customer's complaint and classify it as:\n"
        "- 'Failure-focused' (emphasizing what went wrong),\n"
        "- 'Loss-focused' (emphasizing consequences or damage), or\n"
        "- 'Neutral' (not clearly emotional or blame-oriented).\n"
        "Return only the label."
    )
    res = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text}],
        max_tokens=5, temperature=0
    )
    return res.choices[0].message.content.strip()

def detect_language(text: str, api_key: str) -> str:
    client = OpenAI(api_key=api_key)
    prompt = "Detect the language of the following text. Return only the name of the language in English."
    res = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text}],
        max_tokens=5, temperature=0
    )
    return res.choices[0].message.content.strip()

# ------------------------------------------------------------
# Session state initialization
# ------------------------------------------------------------
def init_session():
    keys_defaults = {
        "sentiment": "", "formality": "", "slant": "", "lang": "",
        "draft": "", "translation": "", "length_label": "", "followups": [],
        "mode": "Simple", "tone_choice": "Neutral", "formality_choice": "Professional", "length_choice": "Balanced"
    }
    for k, v in keys_defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

# ------------------------------------------------------------
# Mode Toggle
# ------------------------------------------------------------
st.radio("Mode", ["Simple", "Advanced"], key="mode", horizontal=True)

# ------------------------------------------------------------
# User Inputs
# ------------------------------------------------------------
client_review = st.text_area("Customer Review or Comment", height=140)
insights = st.text_input("Additional Context (optional)")
channel = st.radio("Type of Inquiry", ["Private (Email)", "Public (Review/Tweet)"], key="channel_type")
api_key = st.text_input("OpenAI API Key", type="password")

if st.button("Generate Draft"):
    if not client_review.strip() or not api_key:
        st.error("Please fill in the review and API key.")
    else:
        st.session_state.sentiment = analyze_sentiment(client_review, api_key)
        st.session_state.formality = detect_formality(client_review, api_key)
        st.session_state.slant = classify_slant(client_review, api_key)
        st.session_state.lang = detect_language(client_review, api_key)

        word_count = len(client_review.split())
        for lower, upper, label in LENGTH_CATEGORIES:
            if lower <= word_count <= upper:
                st.session_state.length_label = label
                break

        # Advanced Mode: use manual settings
        tone = st.session_state.tone_choice if st.session_state.mode == "Advanced" else ""
        formality = st.session_state.formality_choice if st.session_state.mode == "Advanced" else ""
        length = st.session_state.length_choice if st.session_state.mode == "Advanced" else st.session_state.length_label

        system_prompt = f"""
        You are a customer service specialist in life insurance.
        Respond to the customer message in a tone appropriate for a {st.session_state.channel_type.lower()}.
        Sentiment: {st.session_state.sentiment}
        Formality: {formality or st.session_state.formality}
        Complaint Slant: {st.session_state.slant}
        Length: {length}
        Tone: {tone or 'Neutral'}

        Guidelines:
        - Always be empathetic and professional.
        - Acknowledge the customer’s emotion based on sentiment.
        - If slant is 'Failure-focused', focus on empathetic apology.
        - If slant is 'Loss-focused', emphasize concrete remedy or compensation.
        - Use clear insurance terminology.
        - Restate core issue briefly and offer next steps.
        - For public responses, be concise, polite, and careful of sensitive info.
        - For private responses, be more detailed and action-oriented.
        - If the review includes numerical claims or complaints about specific product features (e.g. fee amounts), start the reply with a line beginning with '?' asking the operator to verify the specific product terms. Also use '?' if the request appears unresolved.
        """

        user_message = f"Review: {client_review}\nContext: {insights or '-'}"
        client = OpenAI(api_key=api_key)
        res = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
            max_tokens=500,
            temperature=0.9
        )

        full_output = res.choices[0].message.content.strip()
        lines = full_output.splitlines()
        draft_lines = [l for l in lines if not l.startswith('?')]
        followup_lines = [l[1:].strip() for l in lines if l.startswith('?')]

        st.session_state.draft = "\n".join(draft_lines).strip()
        st.session_state.followups = followup_lines

# ------------------------------------------------------------
# Display Analysis + Controls
# ------------------------------------------------------------
if st.session_state.draft:
    st.markdown("### Analysis Summary")
    st.write(f"**Sentiment:** {st.session_state.sentiment}")
    st.caption("Sentiment is the emotional tone of the review — this helps shape the empathy level and tone of the reply.")
    st.write(f"**Formality (Detected):** {st.session_state.formality}")
    st.caption("This identifies whether the customer wrote casually, neutrally, or formally. It guides the tone and structure of the response.")
    st.write(f"**Complaint Slant:** {st.session_state.slant}")
    st.caption("The slant identifies whether the customer focuses on what went wrong or the losses they suffered — this affects whether the response focuses on empathy or action.")
    st.write(f"**Length (Detected):** {st.session_state.length_label}")
    st.caption("This estimates how long and detailed the customer’s message was, suggesting the expected depth of your reply.")
    st.write(f"**Detected Language:** {st.session_state.lang}")

    if st.session_state.mode == "Advanced":
        st.select_slider("Tone of reply", options=TONE_OPTIONS, key="tone_choice")
        st.select_slider("Length of reply", options=LENGTH_OPTIONS, key="length_choice")
        st.select_slider("Formality of reply", options=FORMALITY_OPTIONS, key="formality_choice")

    st.markdown("---")
    st.header("Draft Response")
    st.text_area("Editable Draft", value=st.session_state.draft, height=200, key="draft_edit")

    st.markdown("### Parameters Used for Draft")
    st.write(f"**Tone:** {st.session_state.tone_choice if st.session_state.mode == 'Advanced' else 'Auto: Neutral (based on sentiment)'}")
    st.write(f"**Formality:** {st.session_state.formality_choice if st.session_state.mode == 'Advanced' else 'Auto: ' + st.session_state.formality}")
    st.write(f"**Length:** {st.session_state.length_choice if st.session_state.mode == 'Advanced' else 'Auto: ' + st.session_state.length_label}")

    if st.session_state.followups:
    st.markdown("### Follow-Up Questions for Operator")
    with st.expander("Click to review", expanded=True):
        for q in st.session_state.followups:
                st.markdown(f"- {q}")

    default_lang = st.session_state.lang if st.session_state.lang in LANGUAGE_OPTIONS else "English"
    final_language = st.selectbox("Translate to:", options=LANGUAGE_OPTIONS, index=LANGUAGE_OPTIONS.index(default_lang))

    if st.button("Translate Final Version"):
        translation_prompt = f"You are a translator. Translate the reply into {final_language}, using accurate grammar and terminology used in insurance and financial services in that language. Prioritize clear, formal phrasing and ensure the meaning and tone match the original English response."
        client = OpenAI(api_key=api_key)
        trans_res = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "system", "content": translation_prompt}, {"role": "user", "content": st.session_state.draft}],
            max_tokens=1000,
            temperature=0
        )
        st.session_state.translation = trans_res.choices[0].message.content.strip()

# ------------------------------------------------------------
# Display Translation
# ------------------------------------------------------------
if st.session_state.translation:
    st.header("Translated Response")
    st.text_area("Final Translation", value=st.session_state.translation, height=200, key="translated_output")
