# Empathos

**Your Voice, Their Peace of Mind**

Empathos is a Streamlit application that helps life‑insurance teams craft empathetic, compliant replies to policyholder reviews—specifically for unit‑linked products—using OpenAI’s GPT‑4.1 (for drafting) and GPT‑4.1‑mini (for translation).

---

## 🚀 Features

- **Sentiment‑Driven Tone Slider** (–5 … +5)  
  Automatically suggests a default reply tone based on the customer’s sentiment, with a manual slider to fine‑tune.

- **Draft Generation** (GPT‑4.1)  
  Generates an empathetic, expert reply that references policy terms (premiums, fund performance, surrender value) and stays compliance‑safe.

- **Regenerate Button**  
  Adjust tone or wording and click “Regenerate Draft” to save on API calls.

- **Final Translation** (GPT‑4.1‑mini)  
  Translate your edited draft into one of 9 supported languages, preserving industry‑specific terminology.

- **In‑App API Key Entry**  
  Securely enter your OpenAI key at runtime—no secrets in source control.

---

## 📦 Requirements

- Python 3.8 or higher  
- An OpenAI API key

---

## 🛠️ Installation

1. **Clone the repo**  
   ```bash
   git clone https://github.com/your‑org/empathos.git
   cd empathos
2. **Create & activate a virtual environment**

   ```bash
    python3 -m venv .venv
    source .venv/bin/activate   # macOS/Linux
    .venv\Scripts\activate      # Windows

3. **Install dependencies**

   ```bash
    pip install -r requirements.txt

## 🚩 Usage
1. **Run the app**

   ```bash
    streamlit run app.py

2. **In the browser**

- **Paste your OpenAI API Key into the field at the top.**

- **Enter a policyholder’s review and any additional context.**

- **Adjust the tone slider if desired (default is sentiment‑derived).**

- **Click Generate Draft (or Regenerate Draft) to get your reply.**

- **Choose a language and click Translate Final Version to produce the localized response.**

3. **Copy & use**
Copy the final translated reply into your CRM, support ticket, or policy portal.

## 🔮 (Potential) Next Steps

- Fine‑tune GPT‑4.1 on your own historical replies for brand consistency.
- Add CI/CD (GitHub Actions) with linting and tests.
- Enhance error handling and loading spinners.
- Extend to more channels (email, chat, social media).

## 🤝 Contributing
Contributions, issues, and feature requests are welcome! Feel free to open a pull request or issue.

## 📄 License
This project is released under the MIT License. See LICENSE for details.
