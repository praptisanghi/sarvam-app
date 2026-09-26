import os
import random
import base64
import requests
import streamlit as st

CHAT_URL = "https://api.sarvam.ai/v1/chat/completions"
TTS_URL = "https://api.sarvam.ai/text-to-speech"
CHAT_MODEL = "sarvam-105b"       # free per token
TTS_MODEL = "bulbul:v3"          # cheap per character, covered by free credits
TTS_CHAR_LIMIT = 2200            # stay safely under bulbul:v3's 2500-char cap

LANGUAGE_CODES = {"English": "en-IN", "Hindi": "hi-IN"}
VOICES = ["shubh", "mani", "ritu", "priya", "kavya", "dev"]  # warm, high-quality v3 voices

st.set_page_config(page_title="Bedtime Story AI", page_icon="🌙")


def get_api_key() -> str:
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
        "You are a gentle, imaginative children's bedtime storyteller who never repeats "
        "the same plot, characters, or opening line twice. Your stories are soothing, "
        "age-appropriate, never scary, and always end peacefully with the child character "
        "feeling safe, happy, and sleepy. Avoid violence and anything intense. "
        f"{lang_instruction} "
        "Do not include any preamble, title formatting symbols, or notes - just the story text, "
        "optionally with a short title on the first line."
    )

    # A hidden random seed nudges the model toward a genuinely different story
    # each time, even when name/age/theme are identical to the last request.
    seed_ingredient = random.choice([
        "a tiny surprising detail involving the moon",
        "a small forgotten object that turns out to be magical",
        "an unexpected gentle friend the character meets",
        "a soft sound that guides the character home",
        "a warm color that appears throughout the story",
        "a kind piece of advice from an animal",
    ])

    user_prompt = (
        f"Write a nighttime bedtime story for a {age}-year-old named {name}. "
        f"{name} should be the main character or very close to the heart of the story. "
        f"Theme / topic to weave in: {theme}. "
        f"Also naturally include: {seed_ingredient}. "
        f"Length and style: {word_budget(age)}. "
        "End the story with the character getting cozy and drifting off to sleep."
    )

    return system_prompt, user_prompt


def generate_story(api_key: str, system_prompt: str, user_prompt: str) -> str:
    response = requests.post(
        CHAT_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "api-subscription-key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "model": CHAT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 1.0,  # higher = more variety between generations
        },
        timeout=60,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Sarvam API error {response.status_code}: {response.text}")

    data = response.json()
    message = data["choices"][0]["message"]
    content = message.get("content")

    # Some responses put the actual text in "reasoning_content" instead of "content"
    if not content:
        content = message.get("reasoning_content")

    if not content:
        finish_reason = data["choices"][0].get("finish_reason", "unknown")
        raise RuntimeError(
            f"Sarvam returned an empty story (finish_reason: {finish_reason}). "
            f"This usually means the theme was flagged or too ambiguous - try rephrasing it. "
            f"Raw response: {data}"
        )

    return content.strip()


def chunk_text(text: str, max_chars: int = TTS_CHAR_LIMIT):
    """Split text into TTS-safe chunks, breaking at sentence boundaries where possible."""
    sentences = text.replace("\n", " ").split(". ")
    chunks, current = [], ""
    for s in sentences:
        piece = s if s.endswith((".", "!", "?")) else s + "."
        if len(current) + len(piece) + 1 > max_chars:
            if current:
                chunks.append(current.strip())
            current = piece
        else:
            current += " " + piece
    if current.strip():
        chunks.append(current.strip())
    return chunks


def narrate(api_key: str, text: str, language: str, speaker: str):
    """Returns a list of audio byte strings (WAV), one per chunk."""
    audio_clips = []
    for chunk in chunk_text(text):
        response = requests.post(
            TTS_URL,
            headers={
                "api-subscription-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": chunk,
                "target_language_code": LANGUAGE_CODES[language],
                "speaker": speaker,
                "model": TTS_MODEL,
                "output_audio_codec": "wav",
            },
            timeout=60,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Sarvam TTS error {response.status_code}: {response.text}")
        audio_b64 = response.json()["audios"][0]
        audio_clips.append(base64.b64decode(audio_b64))
    return audio_clips


# ---------- UI ----------

st.title("🌙 Bedtime Story AI")
st.caption("A calm, custom nighttime story - free, powered by Sarvam AI.")

if "story" not in st.session_state:
    st.session_state.story = None
    st.session_state.story_language = "English"

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

    submitted = st.form_submit_button("✨ Create a new story")

if submitted:
    api_key = get_api_key()
    if not api_key:
        st.error("No Sarvam API key found. Add SARVAM_API_KEY in your app's Secrets.")
    else:
        with st.spinner("Writing a cozy story..."):
            try:
                system_prompt, user_prompt = build_prompt(name, int(age), language, theme)
                st.session_state.story = generate_story(api_key, system_prompt, user_prompt)
                st.session_state.story_language = language
            except Exception as e:
                st.error(str(e))

if st.session_state.story:
    st.markdown("---")
    st.markdown(st.session_state.story)
    st.download_button("Download story as .txt", st.session_state.story, file_name=f"{name}_story.txt")

    st.markdown("### 🔊 Narrate this story")
    voice = st.selectbox("Voice", VOICES, key="voice_generated")
    if st.button("Generate narration"):
        api_key = get_api_key()
        with st.spinner("Recording narration..."):
            try:
                clips = narrate(api_key, st.session_state.story, st.session_state.story_language, voice)
                for i, clip in enumerate(clips, 1):
                    label = f"Part {i}" if len(clips) > 1 else "Narration"
                    st.caption(label)
                    st.audio(clip, format="audio/wav")
            except Exception as e:
                st.error(str(e))

st.markdown("---")
with st.expander("🎙️ Narrate any text (not just a generated story)"):
    custom_text = st.text_area("Paste any story or text here", key="custom_text")
    custom_language = st.selectbox("Text language", ["English", "Hindi"], key="custom_lang")
    custom_voice = st.selectbox("Voice", VOICES, key="voice_custom")
    if st.button("Generate narration for this text"):
        api_key = get_api_key()
        if not custom_text.strip():
            st.warning("Paste some text first.")
        elif not api_key:
            st.error("No Sarvam API key found. Add SARVAM_API_KEY in your app's Secrets.")
        else:
            with st.spinner("Recording narration..."):
                try:
                    clips = narrate(api_key, custom_text, custom_language, custom_voice)
                    for i, clip in enumerate(clips, 1):
                        label = f"Part {i}" if len(clips) > 1 else "Narration"
                        st.caption(label)
                        st.audio(clip, format="audio/wav")
                except Exception as e:
                    st.error(str(e))
