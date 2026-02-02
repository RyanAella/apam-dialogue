import streamlit as st
import streamlit.components.v1 as components
import os
from dotenv import load_dotenv

# Import utility functions from new modules
from audio_utils import tts_browser, tts_browser_queued, stt_browser
from scenario_utils import SCENARIOS, load_scenario
from llm_utils import get_chat_response, get_mentor_feedback

# --- INITIAL SETUP ---
load_dotenv()
model = "gpt-4o"

st.set_page_config(page_title="SI Dialogue Lab", layout="centered")
st.title("SI Dialogue Lab")

# --- SESSION STATE INITIALIZATION ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "start_stt" not in st.session_state:
    st.session_state.start_stt = False
if "finished" not in st.session_state:
    st.session_state.finished = False
if "last_spoken" not in st.session_state:
    st.session_state.last_spoken = None
if "current_scenario" not in st.session_state:
    st.session_state.current_scenario = None
if "briefing_spoken" not in st.session_state:
    st.session_state.briefing_spoken = False



# --- 1. SIDEBAR: CENTRAL AUDIO CONTROLS ---
with st.sidebar:
    st.header("Audio Einstellungen")

    st.subheader("Ausgabe (Hören)")
    auto_speak = st.toggle("Alles automatisch vorlesen", value=False)

    # Emergency stop button for all active browser speech synthesis
    if st.button("Alle Sprachausgaben stoppen", use_container_width=True):
        js_code = "<script>window.speechSynthesis.cancel();</script>"
        components.html(js_code, height=0)
        st.rerun()

    # st.divider()    
    # st.subheader("Eingabe (Sprechen)")
    # st.write("Klicken Sie den Button, um die Spracherkennung zu starten.")
    # if st.button("Jetzt Sprechen", use_container_width=True):
        # Trigger flag to inject STT JavaScript after the next rerun
        # st.session_state.start_stt = True

# --- STT TRIGGER ---
# if st.session_state.get("start_stt", False):
    # stt_browser()
    # st.session_state.start_stt = False

# --- 2. DATA LOADING & SCENARIO HANDLING ---
selected_scenario_name = st.selectbox("Wählen Sie ein Szenario:", list(SCENARIOS.keys()))
user_instruction, full_ki_logic, ai_display_name, mentor_instructions = load_scenario(selected_scenario_name)

# --- BRIEFING UI SECTION ---
st.subheader("Briefing für das Gespräch")

with st.status("📋 Ihre Aufgabenstellung & Szenario-Details", expanded=True, state="complete"):
    st.markdown(user_instruction)

# --- 3. AUTO-READ BRIEFING & SESSION STATE INITIALIZATION ---
# This block handles the logic for reading the briefing automatically.
# It runs on every script rerun, checking if the toggle is on and if the
# briefing for the current scenario has already been read.
if auto_speak and not st.session_state.briefing_spoken:
    tts_browser(user_instruction)
    st.session_state.briefing_spoken = True

if st.session_state.current_scenario != selected_scenario_name:
    # Setup initial chat history with system instructions
    wait_instruction = "\n\nWARTE AUF START: Der User wird das Gespräch eröffnen. Reagiere dann direkt in deiner Rolle."
    
    st.session_state.chat_history = [{"role": "system", "content": full_ki_logic + wait_instruction}]
    st.session_state.finished = False
    st.session_state.last_spoken = None # Reset Audio-History
    st.session_state.current_scenario = selected_scenario_name
    st.session_state.briefing_spoken = False # Reset for the new scenario
    st.rerun()

# --- 4. CHAT LOGIC ---
# First, handle new chat input. This adds the user's message and the AI's response
# to the session state.
if not st.session_state.get("finished", False):
    if user_input := st.chat_input("Was möchtest du sagen?"):
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        if auto_speak:
            tts_browser_queued(user_input)
        
        ai_answer = get_chat_response(model, st.session_state.chat_history)
        if ai_answer:
            st.session_state.chat_history.append({"role": "assistant", "content": ai_answer})
            if auto_speak:
                tts_browser_queued(ai_answer)

# --- 5. CHAT DISPLAY ---
# Then, display the entire chat history. Because this runs *after* the input
# logic, it will include the latest messages in the same run.
if len(st.session_state.chat_history) == 1:
    st.info(f"**Bereit für das Gespräch.** Eröffnen Sie den Dialog, indem Sie unten eine Nachricht eingeben oder das Mikrofon nutzen.")

# Render chat messages
for i, message in enumerate(st.session_state.chat_history):
    if message["role"] != "system":
        label = "Du" if message["role"] == "user" else ai_display_name
        with st.chat_message(message["role"]):
            st.write(f"**{label}:** {message['content']}")

# --- 6. END SESSION & ANALYSIS ---
st.divider()
is_finished = st.session_state.get("finished", False)

if not is_finished:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Gespräch zurücksetzen", use_container_width=True):
            del st.session_state.chat_history
            st.rerun()
    with col2:
        if st.button("Beenden & Feedback erhalten", type="primary", use_container_width=True):
            st.session_state.finished = True
            st.rerun()
else:
    # --- MENTOR FEEDBACK SECTION ---
    st.header("Mentor Feedback")
    
    # Generate plaintext transcript for export
    chat_transcript_text = "GESPRÄCHSPROTOKOLL\n" + "="*20 + "\n"
    for m in st.session_state.chat_history:
        if m["role"] != "system":
            label = "Du" if m["role"] == "user" else ai_display_name
            chat_transcript_text += f"{label}: {m['content']}\n\n"

    # Fetch AI analysis if not already stored
    if "mentor_feedback" not in st.session_state:
        with st.spinner("Analysiere das Gespräch..."):
            feedback = get_mentor_feedback(model, mentor_instructions, st.session_state.chat_history, ai_display_name)
            if feedback:
                st.session_state.mentor_feedback = feedback
                # Auto-read feedback if activated
                if auto_speak:
                    tts_browser(feedback)
    
    if "mentor_feedback" in st.session_state:
        st.markdown(st.session_state.mentor_feedback)
        
        # Prepare full export package
        full_export = chat_transcript_text + "\n" + "="*20 + "\nMENTOR FEEDBACK\n" + "="*20 + "\n" + st.session_state.mentor_feedback
        
        col_down1, col_down2 = st.columns(2)
        with col_down1:
            st.download_button(
                label="Protokoll & Feedback herunterladen",
                data=full_export,
                file_name=f"Dialog_Lab_{selected_scenario_name}.txt",
                mime="text/plain",
                use_container_width=True
            )
        with col_down2:
            if st.button("Neues Gespräch beginnen", use_container_width=True):
                for key in ["chat_history", "finished", "mentor_feedback", "current_scenario"]:
                    st.session_state.pop(key, None)
                st.rerun()
