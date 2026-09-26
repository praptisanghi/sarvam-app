import os
import requests
import streamlit as st

API_URL = "https://api.sarvam.ai/v1/chat/completions"
MODEL = "sarvam-105b"  # free per token

st.set_page_config(page_title="Bedtime Story AI", page_icon="🌙")


def get_api_key() -> str:
    # Prefer Streamlit secrets (used when deployed); fall back to env var (used locally)
    key = st.secrets.get("SARVAM_API_KEY", None) if hasattr(st, "secrets") else None
    return key or os.environ.get("SARVAM_API_KEY", "")


def word_budget(age: int) -> str:
    if age <= 4:
        return "very short (120-180 words), extremely simple sentences, lots of gentle repetition"
    elif age <= 7:
        return "short (250-400 words), simple vocabulary, warm and cozy tone"
    elif age <= 10:
        return "medium length (400-600 words), a bit more descriptive, still calm and reassuring"
    else:
        return "600-800 words, richer vocabulary, but still winding down toward a peaceful ending"


def build_prompt(name: str, age: int, language: str, theme: str):
    lang_instruction = {
        "English": "Write the story in simple, warm English.",
        "Hindi": "Write the story in Hindi (Devanagari script), simple and warm.",
    }[language]

    system_prompt = (
        "You are a gentle, imaginative children's bedtime storyteller. "
        "Your stories are soothing, age-appropriate, never scary, and always end "
        "peacefully with the child character feeling safe, happy, and sleepy. "
        "Avoid violence, conflict that isn't gently resolved, and anything intense. "
        f"{lang_instruction} "
        "Do not include any preamble, title formatting symbols, or notes - just the story text, "
        "optionally with a short title on the first line."
    )

    user_prompt = (
        f"Write a nighttime bedtime story for a {age}-year-old named {name}. "
        f"{name} should be the main character or very close to the heart of the story. "
        f"Theme / topic to weave in: {theme}. "
        f"Length and style: {word_budget(age)}. "
        "End the story with the character getting cozy and drifting off to sleep."
    )

    return system_prompt, user_prompt


def generate_story(api_key: str, system_prompt: str, user_prompt: str) -> str:
    response = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "api-subscription-key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.8,
        },
        timeout=60,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Sarvam API error {response.status_code}: {response.text}")
    return response.json()["choices"][0]["message"]["content"].strip()


# ---------- UI ----------

st.title("🌙 Bedtime Story AI")
st.caption("A calm, custom nighttime story - free, powered by Sarvam AI.")

with st.form("story_form"):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Child's name", "Aarav")
    with col2:
        age = st.number_input("Age", min_value=1, max_value=14, value=6)

    language = st.selectbox("Language", ["English", "Hindi"])
    theme = st.text_area(
        "Theme, topic, or moral",
        "a brave little elephant who is scared of thunder",
        help="e.g. 'sharing toys', 'a shy dragon making a friend', 'counting stars'",
    )

    submitted = st.form_submit_button("✨ Create story")

if submitted:
    api_key = get_api_key()
    if not api_key:
        st.error("No Sarvam API key found. Add SARVAM_API_KEY in your app's Secrets (see deployment instructions).")
    else:
        with st.spinner("Writing a cozy story..."):
            try:
                system_prompt, user_prompt = build_prompt(name, int(age), language, theme)
                story = generate_story(api_key, system_prompt, user_prompt)
                st.markdown("---")
                st.markdown(story)
                st.download_button("Download story as .txt", story, file_name=f"{name}_story.txt")
            except Exception as e:
                st.error(str(e))
