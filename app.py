import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
import os
import re
from dotenv import load_dotenv

# --- INITIAL SETUP ---
load_dotenv()
model = "gpt-4o"

st.set_page_config(page_title="SI Dialogue Lab", layout="centered")
st.title("SI Dialogue Lab")

# Initialize session state for tracking audio playback of the briefing
if "briefing_active" not in st.session_state:
    st.session_state.briefing_active = False

# --- 1. SIDEBAR: CENTRAL AUDIO CONTROLS ---
with st.sidebar:
    st.header("Audio Einstellungen")

    st.subheader("Ausgabe (Hören)")
    auto_speak = st.toggle("Antworten automatisch vorlesen", value=False)

    # Emergency stop button for all active browser speech synthesis
    if st.button("Alle Sprachausgaben stoppen", use_container_width=True):
        js_code = "<script>window.speechSynthesis.cancel();</script>"
        components.html(js_code, height=0)
        st.session_state.briefing_active = False
        st.rerun()

    st.divider()
    
    st.subheader("Eingabe (Sprechen)")
    st.write("Klicken Sie den Button, um die Spracherkennung zu starten.")
    if st.button("Jetzt Sprechen", use_container_width=True):
        # Trigger flag to inject STT JavaScript after the next rerun
        st.session_state.start_stt = True

# --- 1a UTILITY FUNCTIONS ---
def extract_role_label(text):
    """Extracts the character name from the scenario prompt for GUI labeling."""match = re.search(r"DU BIST (?:DIE|DER)\s+([A-ZÄÖÜa-zäöü]+)", text)
    if match:
        return match.group(1).strip()
    return "Gesprächspartner*in"

# --- 1b BROWSER AUDIO ENGINE (JAVASCRIPT INJECTION) ---
def tts_browser(text):
    """Uses Web Speech API to read text. Cleans strings for JS compatibility."""
    clean_text = text.replace("'", "\\'").replace("\n", " ")
    js_code = f"""
    <script>
    setTimeout(function() {{
        window.speechSynthesis.cancel();
        var msg = new SpeechSynthesisUtterance('{clean_text}');
        msg.lang = 'de-DE';
        window.speechSynthesis.speak(msg);
    }}, 100);
    </script>
    """
    components.html(js_code, height=0)

def stop_browser_speech():
    """Immediately halts the browser's speech synthesis engine."""
    js_code = """
    <script>
    window.speechSynthesis.cancel();
    </script>
    """
    components.html(js_code, height=0)

def stt_browser():
    """
    Triggers the browser's SpeechRecognition API.
    Captures audio, sends it to the hidden Streamlit widget, and auto-submits the form.
    """
    js_code = """
    <script>
    var recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = 'de-DE';
    recognition.interimResults = false;
    recognition.start();

    recognition.onresult = function(event) {
        var transcript = event.results[0][0].transcript;

        window.parent.postMessage({
            type: 'streamlit:set_widget_value',
            data: { value: transcript, widgetId: 'chat_input' }
        }, '*');

        setTimeout(function() {
            const textArea = window.parent.document.querySelector('textarea[data-testid="stChatInputTextArea"]');
            if (textArea) {
                textArea.value = transcript;
                textArea.dispatchEvent(new Event('input', { bubbles: true }));
                
                const enterEvent = new KeyboardEvent('keydown', {
                    bubbles: true, cancelable: true, key: 'Enter', code: 'Enter', keyCode: 13
                });
                textArea.dispatchEvent(enterEvent);
            }
        }, 300);
    };
    </script>
    """
    components.html(js_code, height=0)

# --- STT TRIGGER ---
if st.session_state.get("start_stt", False):
    stt_browser()
    st.session_state.start_stt = False

# --- 2. DATA LOADING & SCENARIO HANDLING ---
SCENARIOS = {
    "Verspätungen beim Reporting": {
        "scenario": "scenario_reporting.txt",
        "analysis": "analyze_reporting.txt"
    },
    "Frühzeitiges Melden bei Schwierigkeiten": {
        "scenario": "scenario_difficulties.txt",
        "analysis": "analyze_difficulties.txt"
    }
}

selected_scenario_name = st.selectbox("Wählen Sie ein Szenario:", list(SCENARIOS.keys()))
selected_files = SCENARIOS[selected_scenario_name]

# Pathing for scenario and analysis prompt files
scenario_path = os.path.join("prompts", "scenarios", selected_files["scenario"])
analysis_path = os.path.join("prompts", "analysis", selected_files["analysis"])

if os.path.exists(scenario_path):
    with open(scenario_path, "r", encoding="utf-8") as f:
        raw_content = f.read()

    # Parse character name and split system prompt from GUI instructions
    if "partner_de =" in raw_content:
        role_part = raw_content.split("partner_de =")[1]
        ai_display_name = extract_role_label(role_part)
    else:
        ai_display_name = "Gesprächspartner*in"

    content_parts = raw_content.split("### SYSTEM PROMPT ###")
    user_instruction = content_parts[0].replace("### GUI INSTRUCTION ###", "").strip()
    full_ki_logic = content_parts[1].strip() if len(content_parts) > 1 else raw_content
else:
    st.error(f"Szenario-Datei nicht gefunden.")
    st.stop()

if os.path.exists(analysis_path):
    with open(analysis_path, "r", encoding="utf-8") as f:
        mentor_instructions = f.read()
else:
    st.error(f"Analyse-Datei nicht gefunden.")
    st.stop()

# --- BRIEFING UI SECTION ---
st.subheader("Briefing für das Gespräch")

with st.status("📋 Ihre Aufgabenstellung & Szenario-Details", expanded=True, state="complete"):
    st.markdown(user_instruction)
    
    # Toggle button for reading the briefing out loud
    if not st.session_state.briefing_active:
        if st.button("🔊 Briefing vorlesen", key="read_briefing"):
            st.session_state.briefing_active = True
            tts_browser(user_instruction)
            st.rerun()
    else:
        if st.button("🛑 Vorlesen abbrechen", key="stop_briefing"):
            stop_browser_speech()
            st.session_state.briefing_active = False
            st.rerun()

# --- 3. SESSION STATE INITIALIZATION ---
if "current_scenario" not in st.session_state or st.session_state.current_scenario != selected_scenario_name:
    # Setup initial chat history with system instructions
    wait_instruction = "\n\nWARTE AUF START: Der User wird das Gespräch eröffnen. Reagiere dann direkt in deiner Rolle."
    
    st.session_state.chat_history = [{"role": "system", "content": full_ki_logic + wait_instruction}]
    st.session_state.finished = False
    st.session_state.current_scenario = selected_scenario_name
    st.session_state.briefing_active = False
    st.rerun()

# OpenAI Client Setup
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# --- 4. CHAT DISPLAY & AUTO-VOICE ---
if len(st.session_state.chat_history) == 1:
    st.info("Der Raum ist bereit. Bitte eröffnen Sie das Gespräch über das Eingabefeld unten.")

# Automatic Text-to-Speech for the latest AI message
if len(st.session_state.chat_history) > 1:
    last_msg = st.session_state.chat_history[-1]    
    if auto_speak and last_msg["role"] == "assistant":
        if st.session_state.get("last_spoken") != last_msg["content"]:
            tts_browser(last_msg["content"])
            st.session_state.last_spoken = last_msg["content"]

# Render chat messages
for i, message in enumerate(st.session_state.chat_history):
    if message["role"] != "system":
        label = "Du" if message["role"] == "user" else ai_display_name
        with st.chat_message(message["role"]):
            st.write(f"**{label}:** {message['content']}")
            # Manual replay button for each AI message
            if message["role"] == "assistant":
                if st.button(f"Vorlesen", key=f"btn_{i}"):
                    tts_browser(message['content'])

# --- 5. CHAT INPUT LOGIC ---
if not st.session_state.get("finished", False):
    if user_input := st.chat_input("Schreiben Sie Ihre Antwort..."):
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        st.session_state.briefing_active = False
        try:
            response = client.chat.completions.create(
                model=model,
                messages=st.session_state.chat_history
            )
            ai_answer = response.choices[0].message.content
            st.session_state.chat_history.append({"role": "assistant", "content": ai_answer})
            
        except Exception as e:
            st.error(f"Fehler bei der Anfrage: {e}")
        st.rerun()

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
            chat_transcript_list = [m for m in st.session_state.chat_history if m["role"] != "system"]
            mentor_request = [
                {"role": "system", "content": mentor_instructions},
                {"role": "system", "content": f"Gesprächsprotokoll: {str(chat_transcript_list)}"}
            ]
            try:
                resp = client.chat.completions.create(model=model, messages=mentor_request)
                st.session_state.mentor_feedback = resp.choices[0].message.content
            except Exception as e:
                st.error(f"Fehler: {e}")
    
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
