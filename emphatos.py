import streamlit as st
from openai import OpenAI

# ——————————————————————————————————————————————
# Session state initialization
# ——————————————————————————————————————————————
if 'draft_response' not in st.session_state:
    st.session_state['draft_response'] = ""
if 'final_response' not in st.session_state:
    st.session_state['final_response'] = ""

# ——————————————————————————————————————————————
# App config & title
# ——————————————————————————————————————————————
st.set_page_config(page_title="Empathos", layout="centered")
st.title("Empathos")
st.subheader("Your Voice, Their Peace of Mind")

# ——————————————————————————————————————————————
# 1. User inputs
# ——————————————————————————————————————————————
client_review = st.text_area(
    "Policyholder’s Review or Comment",
    placeholder="Enter the policyholder’s feedback…",
    key="client_review"
)
insights = st.text_input(
    "Additional Context (optional)",
    placeholder="E.g. policy number, advisor name…",
    key="insights"
)
api_key = st.text_input(
    "OpenAI API Key",
    type="password",
    placeholder="sk-…",
    key="api_key"
)

# ——————————————————————————————————————————————
# 2. Sentiment analysis + tone slider
# ——————————————————————————————————————————————
@st.cache_data(ttl=3600)
def analyze_sentiment(review: str, api_key: str) -> float:
    client = OpenAI(api_key=api_key)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a sentiment-analysis assistant. "
                "Evaluate the sentiment of the following customer review and respond with "
                "a single number between -1 (very negative) and +1 (very positive), no extra text."
            )
        },
        {"role": "user", "content": review}
    ]
    res = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=messages,
        max_tokens=3
    )
    try:
        return float(res.choices[0].message.content.strip())
    except:
        return 0.0

def map_polarity_to_slider(p: float) -> int:
    if p <= -0.75:
        return -3
    if p <= -0.25:
        return -1
    if p < 0.25:
        return 0
    if p < 0.75:
        return 2
    return 4

# Only analyze if we have input and key
if client_review and api_key:
    polarity = analyze_sentiment(client_review, api_key)
    default_tone = map_polarity_to_slider(polarity)
else:
    default_tone = 0

slider_value = st.slider(
    "Tone adjustment",
    min_value=-5,
    max_value=+5,
    value=default_tone,
    help="–5 = very apologetic … +5 = very enthusiastic"
)

# ——————————————————————————————————————————————
# 3. Generate / Regenerate Draft (GPT‑4.1)
# ——————————————————————————————————————————————
def generate_draft():
    client = OpenAI(api_key=api_key)
    system_prompt = (
        "You are an Expert CUSTOMER SERVICE PROFESSIONAL specializing in unit‑linked life insurance products. "
        "Your goal is to craft answers to policyholder reviews that balance empathy, product expertise, and compliance. "
        "Follow these steps: "
        "1. READ the customer’s feedback closely, noting any mention of premiums, fund performance, surrender options, or policy terms. "
        "2. ACKNOWLEDGE their specific experience (e.g. market volatility, administrative delays, coverage questions) and thank them for choosing our unit‑linked plan. "
        "3. USE clear life‑insurance terminology—premium allocation, policy value, fund switch, surrender value—so they feel you understand their product. "
        "4. PROVIDE concise, customer‑focused guidance (e.g. how to review fund performance, contact their advisor, or submit a claim) without giving unauthorized financial advice. "
        "5. OFFER actionable next steps or resources (e.g. link to the policy portal, contact details for your advisor, FAQs on unit‑linked features). "
        "6. MAINTAIN regulatory compliance: stay factual, avoid guarantees about investment returns, and reference policy documentation where needed. "
        "Keep your tone empathetic, professional, and clear."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            f"Review: {client_review}\n"
            f"Insights: {insights}\n"
            f"Tone adjustment: {slider_value}"
        )}
    ]
    res = client.chat.completions.create(
        model="gpt-4.1",
        messages=messages,
        max_tokens=1000
    )
    st.session_state['draft_response'] = res.choices[0].message.content

# Buttons
col1, col2 = st.columns(2)
with col1:
    if st.button("Generate Draft"):
        if not api_key:
            st.error("Please enter your OpenAI API key.")
        elif not client_review.strip():
            st.error("Please enter a policyholder review.")
        else:
            generate_draft()
with col2:
    if st.button("Regenerate Draft"):
        if not api_key or not client_review.strip():
            # reuse same checks
            if not api_key:
                st.error("Please enter your OpenAI API key.")
            if not client_review.strip():
                st.error("Please enter a policyholder review.")
        else:
            generate_draft()

# ——————————————————————————————————————————————
# 4. Display Draft
# ——————————————————————————————————————————————
st.header("Draft Response (Editable)")
st.text_area(
    "",
    value=st.session_state['draft_response'],
    height=200,
    key="draft_response_area"
)

# ——————————————————————————————————————————————
# 5. Translate Final Version (GPT‑4.1‑mini)
# ——————————————————————————————————————————————
st.header("Translate Final Version")
final_language = st.selectbox(
    "Language of Final Version:",
    ["English", "Slovak", "Italian", "Icelandic", "Hungarian", "German", "Czech", "Polish", "Vulcan"],
    key="final_language"
)

if st.button("Translate Final Version"):
    if not api_key:
        st.error("Please enter your OpenAI API key.")
    elif not st.session_state['draft_response'].strip():
        st.error("Please generate or edit the draft response first.")
    else:
        client = OpenAI(api_key=api_key)
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are an Expert PROFESSIONAL TRANSLATOR. Convert the following text into {final_language} "
                    "with utmost accuracy and precision, preserving industry‑specific terms and clarity."
                )
            },
            {"role": "user", "content": st.session_state['draft_response']}
        ]
        res = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            max_tokens=1000
        )
        st.session_state['final_response'] = res.choices[0].message.content

# ——————————————————————————————————————————————
# 6. Display Final Response
# ——————————————————————————————————————————————
st.subheader("Final Response (Translated)")
st.text_area(
    "",
    value=st.session_state['final_response'],
    height=200,
    key="final_response_area"
)
