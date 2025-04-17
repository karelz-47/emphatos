import json
import streamlit as st
from openai import OpenAI

# ——————————————————————————————————————————————
# Session‑state initialisation
# ——————————————————————————————————————————————
for k in ("draft_response", "follow_up_questions", "final_response"):
    if k not in st.session_state:
        st.session_state[k] = ""

# ——————————————————————————————————————————————
# Page config
# ——————————————————————————————————————————————
st.set_page_config(page_title="Empathos", layout="centered")
st.title("Empathos")
st.subheader("Your Voice, Their Peace of Mind")

# ——————————————————————————————————————————————
# 1  User inputs
# ——————————————————————————————————————————————
client_review = st.text_area(
    "Policyholder’s Review or Comment",
    placeholder="Enter the policyholder’s feedback…",
    key="client_review",
    height=140,
)
insights = st.text_input(
    "Additional Context (optional)",
    placeholder="E.g. policy number, adviser name…",
    key="insights",
)
api_key = st.text_input(
    "OpenAI API Key",
    type="password",
    placeholder="sk‑…",
    key="api_key",
)

# ——————————————————————————————————————————————
# 2  Sentiment, length & formality analysis
# ——————————————————————————————————————————————
@st.cache_data(ttl=3600, show_spinner=False)
def call_chat(messages, api_key, model="gpt-4.1-mini"):
    client = OpenAI(api_key=api_key)
    res = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=20,
        temperature=0,
    )
    return res.choices[0].message.content.strip()


@st.cache_data(ttl=3600, show_spinner=False)
def analyze_sentiment(review, api_key) -> float:
    messages = [
        {"role": "system",
         "content": "Respond with a single number between -1 (very negative) and +1 (very positive)."},
        {"role": "user", "content": review},
    ]
    try:
        return float(call_chat(messages, api_key))
    except Exception:
        return 0.0


@st.cache_data(ttl=3600, show_spinner=False)
def analyze_formality(review, api_key) -> str:
    messages = [
        {"role": "system",
         "content": ("Label the writing style of the following text with one word: "
                     "'casual', 'neutral', or 'formal'.  "
                     "Respond with the single word—no extra text.")},
        {"role": "user", "content": review},
    ]
    out = call_chat(messages, api_key)
    return out.lower().strip()


def sentiment_label(score: float) -> str:
    if score <= -0.75:
        return "Very negative"
    if score <= -0.25:
        return "Negative"
    if score < 0.25:
        return "Neutral"
    if score < 0.75:
        return "Positive"
    return "Very positive"


def map_tone_slider(p: float) -> int:
    if p <= -0.75:
        return -5
    if p <= -0.25:
        return -3
    if p < 0.25:
        return 0
    if p < 0.75:
        return 3
    return 5


def map_length_slider(word_count: int) -> int:
    if word_count <= 30:
        return -5
    if word_count <= 80:
        return 0
    return 5


def map_formality_slider(formality: str) -> int:
    return {"casual": -5, "neutral": 0, "formal": 5}.get(formality, 0)


# Analyse only if review + key available
if client_review and api_key:
    polarity = analyze_sentiment(client_review, api_key)
    default_tone = map_tone_slider(polarity)

    words = len(client_review.split())
    default_length = map_length_slider(words)

    form_label = analyze_formality(client_review, api_key)
    default_formality = map_formality_slider(form_label)

    # Display sentiment
    st.markdown(
        f"**Detected sentiment:** {polarity:+.2f} … {sentiment_label(polarity)}"
    )
else:
    default_tone = default_length = default_formality = 0

# ——————————————————————————————————————————————
# 3  Control sliders
# ——————————————————————————————————————————————
tone_labels = {-5: "Very Apologetic", 0: "Neutral", 5: "Very Enthusiastic"}
length_labels = {-5: "Very Concise", 0: "Balanced", 5: "Very Detailed"}
formality_labels = {-5: "Casual", 0: "Professional", 5: "Formal"}

tone_value = st.slider(
    "Tone",
    min_value=-5,
    max_value=5,
    step=1,
    value=default_tone,
    help="Adjust emotional tone of reply",
)
st.markdown(f"⬆️ **Tone setting:** {tone_labels.get(tone_value, tone_value)}")

length_value = st.slider(
    "Length",
    min_value=-5,
    max_value=5,
    step=1,
    value=default_length,
    help="Concise … Detailed",
)
st.markdown(f"⬆️ **Length setting:** {length_labels.get(length_value, length_value)}")

formality_value = st.slider(
    "Formality",
    min_value=-5,
    max_value=5,
    step=1,
    value=default_formality,
    help="Casual … Formal",
)
st.markdown(
    f"⬆️ **Formality setting:** {formality_labels.get(formality_value, formality_value)}"
)

# ——————————————————————————————————————————————
# 4  Generate / Regenerate draft
# ——————————————————————————————————————————————
def descriptor(val: int, mapping: dict) -> str:
    # Use nearest label (–5, 0, 5) for prompt brevity
    key = -5 if val < -2 else 5 if val > 2 else 0
    return mapping[key]


def generate_draft():
    client = OpenAI(api_key=api_key)

    style_tone = descriptor(tone_value, tone_labels).lower()
    style_length = descriptor(length_value, length_labels).lower()
    style_formality = descriptor(formality_value, formality_labels).lower()

    max_words = 120 + 40 * (length_value // 2)  # ±80 words swing
    max_tokens = int(max_words * 1.4)           # rough conversion

    system_prompt = (
        "You are a customer‑service specialist for unit‑linked life insurance.\n"
        f"Write a reply that is {style_tone}, {style_length}, and written in a {style_formality} style.\n"
        "• Thank the policy‑holder and restate only the issues they explicitly mention—no assumptions.\n"
        "• Explain or clarify those points using correct life‑insurance terms "
        "(premium allocation, fund switch, surrender value, etc.).\n"
        "• Offer one concrete next step or contact, staying compliant (no return guarantees, no unlicensed advice).\n"
        f"• Stay within ≈{max_words} words.\n\n"
        "After the reply, list any *materially significant* follow‑up questions needed to refine it. "
        "If none, write “No follow‑up questions.”\n"
        "Return your output as strict JSON:\n"
        "{\n"
        '  "draft": "<reply text>",\n'
        '  "questions": ["q1", "q2", ...]\n'
        "}"
    )

    user_msg = (
        f"Review: {client_review}\n\n"
        f"Additional context: {insights if insights else '—'}"
    )

    res = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=max_tokens,
        temperature=0.9,
    )
    try:
        data = json.loads(res.choices[0].message.content)
        st.session_state["draft_response"] = data.get("draft", "").strip()
        qs = data.get("questions", [])
        st.session_state["follow_up_questions"] = (
            "\n".join(f"• {q}" for q in qs) if qs else "No follow‑up questions."
        )
    except Exception:
        st.session_state["draft_response"] = res.choices[0].message.content.strip()
        st.session_state["follow_up_questions"] = (
            "⚠️ Couldn’t parse questions automatically."
        )


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
        if not api_key:
            st.error("Please enter your OpenAI API key.")
        elif not client_review.strip():
            st.error("Please enter a policyholder review.")
        else:
            generate_draft()

# ——————————————————————————————————————————————
# 5  Display draft & questions
# ——————————————————————————————————————————————
st.header("Draft Response (Editable)")
st.text_area(
    "",
    value=st.session_state["draft_response"],
    height=220,
    key="draft_response_area",
)

with st.expander("Follow‑up Questions"):
    st.write(st.session_state["follow_up_questions"])

# ——————————————————————————————————————————————
# 6  Translate final version
# ——————————————————————————————————————————————
st.header("Translate Final Version")
final_language = st.selectbox(
    "Language of Final Version:",
    [
        "English",
        "Slovak",
        "Italian",
        "Icelandic",
        "Hungarian",
        "German",
        "Czech",
        "Polish",
        "Vulcan",
    ],
    key="final_language",
)

if st.button("Translate Final Version"):
    if not api_key:
        st.error("Please enter your OpenAI API key.")
    elif not st.session_state["draft_response"].strip():
        st.error("Please generate or edit the draft response first.")
    else:
        translator_prompt = (
            f"You are a professional translator. Render the text into {final_language}, "
            "using clear, natural wording and the insurance terms typically used in that language—even if phrasing differs from the original. "
            "Keep meaning, tone, and compliance intact."
        )
        translated = call_chat(
            [
                {"role": "system", "content": translator_prompt},
                {"role": "user", "content": st.session_state["draft_response"]},
            ],
            api_key,
            model="gpt-4.1-mini",
        )
        st.session_state["final_response"] = translated

# ——————————————————————————————————————————————
# 7  Display final response
# ——————————————————————————————————————————————
st.subheader("Final Response (Translated)")
st.text_area(
    "",
    value=st.session_state["final_response"],
    height=200,
    key="final_response_area",
)
