import os
from openai import OpenAI
import streamlit as st

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
