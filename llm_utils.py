import os
import io
import json
import httpx
import streamlit as st
from openai import OpenAI
from groq import Groq

# --- 1. INITIALIZE CLIENTS ---

def init_openai_client():
    """Initialize the OpenAI client. Returns None if API key is missing."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("OpenAI API-Key nicht gefunden. Bitte setze die Umgebungsvariable OPENAI_API_KEY.")
        return None
    return OpenAI(api_key=api_key)

def init_groq_client():
    """Initialize the Groq client for audio transcription. Returns None if API key is missing."""
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        st.error("Groq API-Key nicht gefunden. Bitte setze die Umgebungsvariable GROQ_API_KEY.")
        return None

    http_client = httpx.Client(
        base_url="https://api.groq.com/openai/v1",
        timeout=httpx.Timeout(60.0, connect=15.0),
        verify=True,
    )
    return Groq(api_key=groq_api_key, http_client=http_client, max_retries=3)

# Initialize clients
client = init_openai_client()
groq_client = init_groq_client()

# --- 2. CHAT FUNCTIONS ---

def get_chat_response(model, history):
    """Get a chat response from OpenAI API. Returns string, never None."""
    if not client:
        return "OpenAI Client ist nicht initialisiert."
    try:
        response = client.chat.completions.create(model=model, messages=history)
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Fehler bei der Anfrage an OpenAI API: {e}")
        return "Fehler bei der Generierung der Antwort."


def get_mentor_feedback(model: str, messages: list) -> str:
    """Get mentor feedback from OpenAI based on prepared messages."""
    if not client:
        return "OpenAI Client ist nicht initialisiert."

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        st.error(f"Fehler bei der Mentor-Analyse: {e}")
        return "Fehler bei der Mentor-Analyse."

    
# --- 3. AUDIO TRANSCRIPTION ---    
def transcribe_audio_via_groq(audio_input):
    """
    Transcribe audio using Groq Whisper.
    Accepts bytes, UploadedFile, BytesIO, or Streamlit audio objects.
    Returns string or None.
    """

    if not groq_client:
        return None

    if not audio_input:
        return None

    # --- Normalize to raw bytes ---
    audio_bytes = None

    # Case 1: raw bytes
    if isinstance(audio_input, (bytes, bytearray)):
        audio_bytes = audio_input

    # Case 2: UploadedFile / BytesIO
    elif hasattr(audio_input, "read"):
        audio_bytes = audio_input.read()

    # Case 3: Streamlit ChatInputValue.audio (dict-like)
    elif isinstance(audio_input, dict):
        audio_bytes = audio_input.get("data")

    if not audio_bytes or not isinstance(audio_bytes, (bytes, bytearray)) or len(audio_bytes) < 100:
        st.warning("Audio-Aufnahme war zu kurz oder leer.")
        return None

    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "input.wav"
        audio_file.seek(0)

        with st.spinner("Transkribiere Audio…"):
            transcription = groq_client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3",
                response_format="text"
            )

        # Groq may return str or object depending on SDK version
        if isinstance(transcription, str):
            return transcription.strip()

        return getattr(transcription, "text", None)

    except Exception as e:
        st.error(f"Fehler bei der Transkription: {e}")
        return None
