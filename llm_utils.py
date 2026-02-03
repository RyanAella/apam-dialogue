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


def get_mentor_feedback(model, instructions, chat_history, ai_display_name):
    """Get mentor feedback from OpenAI based on chat transcript."""
    if not client:
        return "OpenAI Client ist nicht initialisiert."
    try:
        # Filter system messages
        chat_transcript_list = [m for m in chat_history if m["role"] != "system"]
        # Format transcript nicely for GPT
        formatted_transcript = json.dumps(chat_transcript_list, indent=2, ensure_ascii=False)

        mentor_request = [
            {"role": "system", "content": instructions},
            {"role": "system", "content": f"Gesprächsprotokoll:\n{formatted_transcript}"}
        ]

        response = client.chat.completions.create(model=model, messages=mentor_request)
        return response.choices[0].message.content

    except Exception as e:
        st.error(f"Fehler bei der Analyse durch OpenAI API: {e}")
        return "Fehler bei der Mentor-Analyse."
    
# --- 3. AUDIO TRANSCRIPTION ---
    
def transcribe_audio_via_groq(audio_bytes):
    """Transcribe audio using Groq Whisper. Returns string text."""
    if not groq_client:
        return "Groq Client ist nicht initialisiert."
    if not audio_bytes or len(audio_bytes) < 100:
        st.warning("Audio-Aufnahme war zu kurz oder leer.")
        return None

    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "input.wav"
        audio_file.seek(0)

        with st.spinner("Transkribiere Audio… Dies kann einige Momente dauern."):
            transcription = groq_client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3",
                response_format="text"
            )

        # Return only the text
        return transcription.text if hasattr(transcription, "text") else transcription

    except Exception as e:
        st.error(f"Fehler bei der Transkription: {e}")
        return None
