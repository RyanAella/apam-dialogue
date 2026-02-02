import os
from openai import OpenAI
import streamlit as st
import io
import httpx
from groq import Groq

# Initialize the OpenAI client
try:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        st.stop()
    client = OpenAI(api_key=api_key)
except Exception as e:
    st.error(f"Failed to initialize OpenAI client: {e}")
    st.stop()

# Initialize the Groq client for audio transcription
try:
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        st.error("Groq API key not found. Please set the GROQ_API_KEY environment variable.")
        st.stop()
    
    http_client = httpx.Client(
        base_url="https://api.groq.com/openai/v1",
        timeout=httpx.Timeout(60.0, connect=15.0),
        verify=True,
    )
    
    groq_client = Groq(
        api_key=groq_api_key,
        http_client=http_client,
        max_retries=3
    )
except Exception as e:
    st.error(f"Failed to initialize Groq client: {e}")
    st.stop()

def get_chat_response(model, history):
    """Gets a chat response from the OpenAI API."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=history
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Fehler bei der Anfrage an die OpenAI API: {e}")
        return None

def get_mentor_feedback(model, instructions, chat_history, ai_display_name):
    """Gets mentor feedback based on the chat transcript."""
    try:
        # Generate plaintext transcript for analysis
        chat_transcript_list = [m for m in chat_history if m["role"] != "system"]
        
        mentor_request = [
            {"role": "system", "content": instructions},
            {"role": "system", "content": f"Gesprächsprotokoll: {str(chat_transcript_list)}"}
        ]
        
        response = client.chat.completions.create(
            model=model,
            messages=mentor_request
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Fehler bei der Analyse durch die OpenAI API: {e}")
        return None
    
def transcribe_audio_via_groq(audio_bytes):
    """Transcribes audio using the Groq API."""
    if not audio_bytes or len(audio_bytes) < 100:
        st.warning("Audio-Aufnahme war zu kurz oder leer.")
        return None
        
    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "input.wav" 
        
        st.warning("Transkribiere Audio... Dies kann einige Momente dauern.")

        transcription = groq_client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-large-v3",
            response_format="text"
        )
        return transcription
        
    except Exception as e:
        st.error(f"Fehler bei der Transkription: {e}")
        return None
