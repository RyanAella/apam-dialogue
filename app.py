import time
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
import os
import json, re
from dotenv import load_dotenv

# --- INITIAL SETUP ---
load_dotenv()
model = "gpt-4o"

st.set_page_config(page_title="SI Dialogue Lab", layout="centered")
st.title("SI Dialogue Lab")

# --- SESSION STATE INITIALIZATION ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "finished" not in st.session_state:
    st.session_state.finished = False
if "last_spoken" not in st.session_state:
    st.session_state.last_spoken = None

# --- 1. SIDEBAR: CENTRAL AUDIO CONTROLS ---
with st.sidebar:
    st.header("Audio Einstellungen")
    auto_speak = st.toggle("Antworten automatisch vorlesen", value=False)

    if st.button("Alle Sprachausgaben stoppen", use_container_width=True):
        components.html("<script>window.speechSynthesis.cancel();</script>", height=0)
        st.rerun()

# --- 1a UTILITY FUNCTIONS ---
def extract_role_label(text):
    """Extracts the character name from the scenario prompt for GUI labeling."""
    match = re.search(r"DU BIST (?:DIE|DER)\s+([A-ZÄÖÜa-zäöü]+)", text)
    return match.group(1) if match else "Gesprächspartner*in"

# --- 1b BROWSER AUDIO ENGINE (JAVASCRIPT INJECTION) ---
def format_for_tts(text: str) -> str:
    # Listen / Aufzählungen
    text = re.sub(r"\n\s*[-•]\s*", ". ", text)

    # Absatzumbrüche → deutliche Pause
    text = re.sub(r"\n{2,}", ". ", text)

    # Einzelne Zeilenumbrüche → kurze Pause
    text = text.replace("\n", " ")

    # Whitespace normalisieren
    text = re.sub(r"\s+", " ", text)

    return text.strip()

def tts_browser(text):
    """Uses Web Speech API to read text. Cleans strings for JS compatibility."""
    if not text:
        return
    
    tts_text = format_for_tts(text)

    clean_text = json.dumps(tts_text)

    js_code = f"""
    <script>
    (function() {{
        window.speechSynthesis.cancel(); 
        var msg = new SpeechSynthesisUtterance({clean_text});
        msg.lang = 'de-DE';
        window.speechSynthesis.speak(msg);
    }})();
    </script>
    """
    components.html(js_code, height=0)

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

    col_audio, _ = st.columns([1, 2])
    with col_audio:
        if st.button("🔊 Briefing vorlesen", key="read_briefing"):
            tts_browser(user_instruction)

# --- 3. SESSION STATE INITIALIZATION ---
if "current_scenario" not in st.session_state or st.session_state.current_scenario != selected_scenario_name:
    # Setup initial chat history with system instructions
    wait_instruction = "\n\nWARTE AUF START: Der User wird das Gespräch eröffnen. Reagiere dann direkt in deiner Rolle."
    
    st.session_state.chat_history = [{"role": "system", "content": full_ki_logic + wait_instruction}]
    st.session_state.finished = False
    st.session_state.last_spoken = None # Reset Audio-History
    st.session_state.current_scenario = selected_scenario_name
    st.rerun()

# OpenAI Client Setup
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# --- 4. CHAT DISPLAY & AUTO-VOICE ---
if len(st.session_state.chat_history) == 1:
    st.info(f"**Bereit für das Gespräch.** Eröffnen Sie den Dialog, indem Sie unten eine Nachricht eingeben oder das Mikrofon nutzen.")

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

# Automatic Text-to-Speech for the latest AI message
if auto_speak and len(st.session_state.chat_history) > 1:
    last_msg = st.session_state.chat_history[-1]
    if last_msg["role"] == "assistant" and st.session_state.last_spoken != last_msg["content"]:
        tts_browser(last_msg["content"])
        st.session_state.last_spoken = last_msg["content"]

# --- CHAT INPUT ---
user_input = st.chat_input("Schreiben Sie Ihre Antwort...")

# --- 🎤 MICROPHONE (PURE JS, WORKING) ---
components.html(
    """
    <div style="text-align:right; margin-top:-60px; margin-bottom:20px;">
      <button id="micBtn" style="
        font-size:20px;
        padding:6px 10px;
        border-radius:50%;
        cursor:pointer;
      ">🎤</button>
    </div>

    <script>
    const btn = document.getElementById("micBtn");

    btn.onclick = () => {
        if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
            alert("Spracherkennung wird nicht unterstützt.");
            return;
        }

        const rec = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        rec.lang = 'de-DE';
        rec.interimResults = false;

        rec.onresult = e => {
            const text = e.results[0][0].transcript;
            const ta = window.parent.document.querySelector(
                'textarea[data-testid="stChatInputTextArea"]'
            );
            if (ta) {
                ta.value = text;
                ta.dispatchEvent(new Event('input', { bubbles: true }));
            }
        };

        rec.start();
    };
    </script>
    """,
    height=80
)

# --- OPENAI CALL ---
if user_input and not st.session_state.finished:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=model,
        messages=st.session_state.chat_history
    )
    ai_text = response.choices[0].message.content
    st.session_state.chat_history.append({"role": "assistant", "content": ai_text})
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
