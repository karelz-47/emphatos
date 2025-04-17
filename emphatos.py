"""Empathos – streamlined Streamlit front‑end All widgets now have non‑empty labels (hidden if necessary) so Streamlit ≥ 1.33 shows no accessibility warnings. Minor defensive tweaks included. """

from future import annotations

import json import streamlit as st from openai import OpenAI

——————————————————————————————————————————————

Constants & helper mappings

——————————————————————————————————————————————

TONE_LABELS = {-5: "Very Apologetic", 0: "Neutral", 5: "Very Enthusiastic"} LENGTH_LABELS = {-5: "Very Concise", 0: "Balanced", 5: "Very Detailed"} FORMALITY_LABELS = {-5: "Casual", 0: "Professional", 5: "Formal"}

——————————————————————————————————————————————

Session‑state initialisation

——————————————————————————————————————————————

for key in ("draft_response", "follow_up_questions", "final_response"): st.session_state.setdefault(key, "")

——————————————————————————————————————————————

Page config

——————————————————————————————————————————————

st.set_page_config(page_title="Empathos", layout="centered") st.title("Empathos") st.subheader("Your Voice, Their Peace of Mind")

——————————————————————————————————————————————

1  User inputs

——————————————————————————————————————————————

client_review = st.text_area( label="Policyholder’s Review or Comment", placeholder="Enter the policyholder’s feedback…", key="client_review", height=140, ) insights = st.text_input( label="Additional Context (optional)", placeholder="E.g. policy number, adviser name…", key="insights", ) api_key = st.text_input( label="OpenAI API Key", type="password", placeholder="sk‑…", key="api_key", )

Guard against missing key early to avoid repeated checks

if api_key == "": st.warning("Enter your OpenAI API key to enable analysis and drafting.")

——————————————————————————————————————————————

2  Sentiment, length & formality analysis

——————————————————————————————————————————————

def call_chat(messages: list[dict[str, str]], *, model: str = "gpt-4.1-mini") -> str: """Wrapper with bare‑bones error handling; returns empty string on failure.""" try: client = OpenAI(api_key=api_key) res = client.chat.completions.create( model=model, messages=messages, max_tokens=20, temperature=0, ) return res.choices[0].message.content.strip() except Exception as exc:  # noqa: BLE001 st.error(f"OpenAI error: {exc}") return ""

@st.cache_data(ttl=3600, show_spinner=False) def analyze_sentiment(review: str) -> float: messages = [ {"role": "system", "content": "Respond with one number between -1 and 1."}, {"role": "user", "content": review}, ] try: return float(call_chat(messages)) except ValueError: return 0.0

@st.cache_data(ttl=3600, show_spinner=False) def analyze_formality(review: str) -> str: messages = [ { "role": "system", "content": ( "Classify the style as 'casual', 'neutral', or 'formal' and respond with the single word only." ), }, {"role": "user", "content": review}, ] return call_chat(messages).lower()

def sentiment_label(score: float) -> str: if score <= -0.75: return "Very negative" if score <= -0.25: return "Negative" if score < 0.25: return "Neutral" if score < 0.75: return "Positive" return "Very positive"

def map_tone_slider(p: float) -> int: if p <= -0.75: return -5 if p <= -0.25: return -3 if p < 0.25: return 0 if p < 0.75: return 3 return 5

def map_length_slider(word_count: int) -> int: if word_count <= 30: return -5 if word_count <= 80: return 0 return 5

def map_formality_slider(formality: str) -> int: return {"casual": -5, "neutral": 0, "formal": 5}.get(formality, 0)

Analyse only if review & key are provided

if client_review and api_key: polarity = analyze_sentiment(client_review) default_tone = map_tone_slider(polarity)

word_count = len(client_review.split())
default_length = map_length_slider(word_count)

form_style = analyze_formality(client_review)
default_formality = map_formality_slider(form_style)

st.markdown(
    f"**Detected sentiment:** {polarity:+.2f} … {sentiment_label(polarity)}"
)

else: default_tone = default_length = default_formality = 0

——————————————————————————————————————————————

3  Control sliders

——————————————————————————————————————————————

tone_value = st.slider( label="Tone", min_value=-5, max_value=5, step=1, value=default_tone, help="Adjust emotional tone of reply", ) st.markdown(f"⬆️ Tone setting: {TONE_LABELS.get(tone_value, tone_value)}")

length_value = st.slider( label="Length", min_value=-5, max_value=5, step=1, value=default_length, help="Concise … Detailed", ) st.markdown(f"⬆️ Length setting: {LENGTH_LABELS.get(length_value, length_value)}")

formality_value = st.slider( label="Formality", min_value=-5, max_value=5, step=1, value=default_formality, help="Casual … Formal", ) st.markdown( f"⬆️ Formality setting: {FORMALITY_LABELS.get(formality_value, formality_value)}" )

——————————————————————————————————————————————

4  Draft generation helpers

——————————————————————————————————————————————

def descriptor(val: int, mapping: dict[int, str]) -> str:  # noqa: D401 "Return nearest word descriptor for slider value (use -5/0/5 only)." key = -5 if val < -2 else 5 if val > 2 else 0 return mapping[key]

def generate_draft() -> None:  # noqa: C901 – little long but readable if not api_key: st.error("OpenAI API key missing.") return

client = OpenAI(api_key=api_key)

style_tone = descriptor(tone_value, TONE_LABELS).lower()
style_length = descriptor(length_value, LENGTH_LABELS).lower()
style_formality = descriptor(formality_value, FORMALITY_LABELS).lower()

base_words = 120
max_words = base_words + 40 * (length_value // 2)  # ±80‑word swing
max_tokens = int(max_words * 1.5)  # generous safety margin

system_prompt = (
    "You are a customer‑service specialist for unit‑linked life insurance.\n"
    f"Write a reply that is {style_tone}, {style_length}, and written in a {style_formality} style.\n"
    "• Thank the policy‑holder and restate only the issues they explicitly mention—no assumptions.\n"
    "• Explain or clarify those points using correct life‑insurance terms (premium allocation, fund switch, surrender value, etc.).\n"
    "• Offer one concrete next step or contact, staying compliant (no return guarantees, no unlicensed advice).\n"
    f"• Stay within ≈{max_words} words.\n\n"
    "After the reply, list any *materially significant* follow‑up questions needed to refine it. If none, write 'No follow‑up questions.'\n"
    "Return your output as strict JSON like {\"draft\": <text>, \"questions\": [...]}."
)

user_msg = (
    f"Review: {client_review}\n\n"
    f"Additional context: {insights if insights else '—'}"
)

try:
    res = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=max_tokens,
        temperature=0.9,
    )
    raw_out = res.choices[0].message.content
    data = json.loads(raw_out)
    st.session_state["draft_response"] = data.get("draft", "").strip()
    qs = data.get("questions", [])
    st.session_state["follow_up_questions"] = (
        "\n".join(f"• {q}" for q in qs) if qs else "No follow‑up questions."
    )
except (json.JSONDecodeError, KeyError):
    st.session_state["draft_response"] = raw_out.strip()
    st.session_state["follow_up_questions"] = "⚠️ Couldn’t parse follow‑up questions automatically."

——————————————————————————————————————————————

5  Action buttons

——————————————————————————————————————————————

col1, col2 = st.columns(2) with col1: if st.button("Generate Draft"): if not client_review.strip(): st.error("Please enter a policyholder review.") else: generate_draft() with col2: if st.button("Regenerate Draft"): if not client_review.strip(): st.error("Please enter a policyholder review.") else: generate_draft()

——————————————————————————————————————————————

6  Display draft & questions

——————————————————————————————————————————————

st.header("Draft Response (Editable)") st.text_area( label="draft_response_display",  # non‑empty label for accessibility value=st.session_state["draft_response"], height=220, key="draft_response_area", label_visibility="collapsed", )

with st.expander("Follow‑up Questions"): st.write(st.session_state["follow_up_questions"])

——————————————————————————————————————————————

7  Translate final version

——————————————————————————————————————————————

st.header("Translate Final Version") final_language = st.selectbox( label="Language of Final Version:", options=[ "English", "Slovak", "Italian", "Icelandic", "Hungarian", "German", "Czech", "Polish", "Vulcan", ], key="final_language", )

if st.button("Translate Final Version"): if not st.session_state["draft_response"].strip(): st.error("Please generate or edit the draft response first.") elif not api_key: st.error("Please enter your OpenAI API key.") else: translator_prompt = ( f"You are a professional translator. Render the text into {final_language}, " "using clear, natural wording and the insurance terms typically used in that language—even if phrasing differs from the original. " "Keep meaning, tone, and compliance intact." ) translated = call_chat( [ {"role": "system", "content": translator_prompt}, {"role": "user", "content": st.session_state["draft_response"]}, ] ) st.session_state["final_response"] = translated

——————————————————————————————————————————————

8  Display final response

——————————————————————————————————————————————

st.subheader("Final Response (Translated)") st.text_area( label="final_response_display",  # non‑empty label value=st.session_state["final_response"], height=200, key="final_response_area", label_visibility="collapsed", )

