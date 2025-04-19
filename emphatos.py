import streamlit as st
from openai import OpenAI

# ------------------------------------------------------------
# Page config
# ------------------------------------------------------------
st.set_page_config(page_title="Empathos", layout="centered")
st.title("Empathos")
st.subheader("Your Voice, Their Peace of Mind")

# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------
def get_openai_client(api_key: str):
    return OpenAI(api_key=api_key)

@st.cache_data(ttl=3600)
def analyze_sentiment(text: str, client) -> tuple:
    prompt = """Label the sentiment of the following customer message as one of:
    'Very negative', 'Negative', 'Neutral', 'Positive', 'Very positive'.
    Return only the label."""
    res = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
        max_tokens=5,
        temperature=0
    )
    return res.choices[0].message.content.strip()

@st.cache_data(ttl=3600)
def detect_formality(text: str, client) -> str:
    prompt = """Classify the formality of this message as 'Casual', 'Neutral', or 'Formal'."""
    res = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
        max_tokens=5,
        temperature=0
    )
    return res.choices[0].message.content.strip()

@st.cache_data(ttl=3600)
def classify_slant(text: str, client) -> str:
    prompt = (
        "Analyze the customer's complaint and classify it as:\n"
        "- 'Failure-focused' (emphasizing what went wrong),\n"
        "- 'Loss-focused' (emphasizing consequences or damage), or\n"
        "- 'Neutral' (not clearly emotional or blame-oriented).\n"
        "Return only the label."
    )
    res = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
        max_tokens=5,
        temperature=0
    )
    return res.choices[0].message.content.strip()

@st.cache_data(ttl=3600)
def detect_language(text: str, client) -> str:
    prompt = "Detect the language of the following text. Return only the name of the language in English."
    res = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
        max_tokens=5,
        temperature=0
    )
    return res.choices[0].message.content.strip()

# ------------------------------------------------------------
# User Inputs
# ------------------------------------------------------------
client_review = st.text_area("Customer Review or Comment", height=140)
insights = st.text_input("Additional Context (optional)")
channel = st.radio("Type of Inquiry", ["Private (Email)", "Public (Review/Tweet)"])
api_key = st.text_input("OpenAI API Key", type="password")

# ------------------------------------------------------------
# Generate Draft Response
# ------------------------------------------------------------
if st.button("Generate Draft"):
    if not client_review.strip() or not api_key:
        st.error("Please fill in the review and API key.")
    else:
        client = get_openai_client(api_key)

        sentiment = analyze_sentiment(client_review, client)
        formality = detect_formality(client_review, client)
        slant = classify_slant(client_review, client)
        lang = detect_language(client_review, client)

        system_prompt = f"""
        You are a customer service specialist in life insurance.
        Respond to the customer message in a tone appropriate for a {channel.lower()}.
        Sentiment: {sentiment}
        Formality: {formality}
        Complaint Slant: {slant}

        Guidelines:
        - Always be empathetic and professional.
        - Acknowledge the customer’s emotion based on sentiment.
        - If slant is 'Failure-focused', focus on empathetic apology.
        - If slant is 'Loss-focused', emphasize concrete remedy or compensation.
        - Use clear insurance terminology.
        - Restate core issue briefly and offer next steps.
        - For public responses, be concise, polite, and careful of sensitive info.
        - For private responses, be more detailed and action-oriented.
        """

        user_message = f"Review: {client_review}\nContext: {insights or '-'}"
        res = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=500,
            temperature=0.9
        )

        draft = res.choices[0].message.content.strip()
        st.session_state.draft = draft
        st.session_state.lang = lang

# ------------------------------------------------------------
# Display Draft
# ------------------------------------------------------------
if "draft" in st.session_state:
    st.header("Draft Response")
    st.text_area("Editable Draft", value=st.session_state.draft, height=200, key="draft_edit")

    # Auto-select translation language based on input language
    lang_options = ["English","Slovak","Italian","Icelandic","Hungarian","German","Czech","Polish","Vulcan"]
    default_lang = st.session_state.lang if st.session_state.lang in lang_options else "English"
    final_language = st.selectbox("Translate to:", options=lang_options, index=lang_options.index(default_lang))

    if st.button("Translate Final Version"):
        translation_prompt = f"You are a translator. Translate the reply into {final_language}, using clear language and insurance-specific terms."
        client = get_openai_client(api_key)
        trans_res = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": translation_prompt},
                {"role": "user", "content": st.session_state.draft},
            ],
            max_tokens=1000,
            temperature=0
        )
        st.session_state.translation = trans_res.choices[0].message.content.strip()

# ------------------------------------------------------------
# Display Translation
# ------------------------------------------------------------
if "translation" in st.session_state:
    st.header("Translated Response")
    st.text_area("Final Translation", value=st.session_state.translation, height=200, key="translated_output")
