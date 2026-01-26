import time
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
import os
import json, re
from dotenv import load_dotenv

# --- 1. INITIAL SETUP ---
load_dotenv()
model = "gpt-4o"
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

st.set_page_config(page_title="SI Dialogue Lab", layout="centered")
st.title("SI Dialogue Lab")

# Hidden CSS for the Receiver
st.markdown("<style>div[data-testid='stTextInput']:has(input[aria-label='STT Receiver']) {display: none;}</style>", unsafe_allow_html=True)

# --- 2. SESSION STATE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "finished" not in st.session_state:
    st.session_state.finished = False
if "last_spoken" not in st.session_state:
    st.session_state.last_spoken = None

# --- 3. AI PROCESSING LOGIC ---
def process_ai_response(text):
    """Dies ist der Motor des Dialogs."""
    if text and not st.session_state.finished:
        # User Nachricht hinzufügen
        st.session_state.chat_history.append({"role": "user", "content": text})
        
        # KI Antwort generieren
        with st.spinner("KI überlegt..."):
            response = client.chat.completions.create(model=model, messages=st.session_state.chat_history)
            ai_text = response.choices[0].message.content
            st.session_state.chat_history.append({"role": "assistant", "content": ai_text})
        
        # Seite neu laden, um Chat anzuzeigen
        st.rerun()

def handle_voice_input():
    """Wird sofort aufgerufen, wenn JS Text sendet."""
    val = st.session_state.speech_input_receiver
    if val:
        st.session_state.speech_input_receiver = "" # Feld leeren
        process_ai_response(val)

# --- 4. DER TRIGGER (WICHTIGSTE ZEILE) ---
# Dieser Receiver fängt die Daten vom JavaScript ab
st.text_input("STT Receiver", key="speech_input_receiver", on_change=handle_voice_input, label_visibility="collapsed")

# --- 5. SCENARIO LOGIC ---
SCENARIOS = {
    "Verspätungen beim Reporting": {"scenario": "scenario_reporting.txt", "analysis": "analyze_reporting.txt"},
    "Frühzeitiges Melden bei Schwierigkeiten": {"scenario": "scenario_difficulties.txt", "analysis": "analyze_difficulties.txt"}
}

selected_scenario_name = st.selectbox("Wählen Sie ein Szenario:", list(SCENARIOS.keys()))
selected_files = SCENARIOS[selected_scenario_name]

# Pfade laden
scenario_path = os.path.join("prompts", "scenarios", selected_files["scenario"])
analysis_path = os.path.join("prompts", "analysis", selected_files["analysis"])

if os.path.exists(scenario_path):
    with open(scenario_path, "r", encoding="utf-8") as f:
        raw_content = f.read()
    
    # AI Name extrahieren
    match = re.search(r"DU BIST (?:DIE|DER)\s+([A-ZÄÖÜa-zäöü]+)", raw_content)
    ai_display_name = match.group(1) if match else "Gesprächspartner*in"

    content_parts = raw_content.split("### SYSTEM PROMPT ###")
    user_instruction = content_parts[0].replace("### GUI INSTRUCTION ###", "").strip()
    full_ki_logic = content_parts[1].strip() if len(content_parts) > 1 else raw_content
else:
    st.error("Szenario-Datei nicht gefunden.")
    st.stop()

# Initialisierung des Chats bei Szenario-Wechsel
if "current_scenario" not in st.session_state or st.session_state.current_scenario != selected_scenario_name:
    st.session_state.chat_history = [{"role": "system", "content": full_ki_logic + "\n\nAntworte direkt in deiner Rolle."}]
    st.session_state.finished = False
    st.session_state.current_scenario = selected_scenario_name
    st.rerun()

# --- 6. UI: CHAT & AUDIO ---
st.subheader("Briefing")
st.info(user_instruction)

# Chat Verlauf anzeigen
for i, message in enumerate(st.session_state.chat_history):
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.write(f"**{ai_display_name if message['role']=='assistant' else 'Du'}:** {message['content']}")

# Text Eingabe (Fallback)
user_text = st.chat_input("Tippen Sie hier...")
if user_text:
    process_ai_response(user_text)

# --- 7. DAS MIKROFON (JAVASCRIPT) ---
st.markdown("### 🎤 Spracheingabe")
components.html("""
    <div style="display:flex; align-items:center; gap:10px;">
      <button id="micBtn" style="font-size:16px; padding:10px 16px; border-radius:8px; cursor:pointer; background-color:#f0f2f6; border:1px solid #ddd;">
        🎤 Jetzt sprechen
      </button>
      <span id="status" style="font-family:sans-serif; font-size:13px; color:#555;">Bereit.</span>
    </div>
    <script>
    const btn = document.getElementById("micBtn");
    const status = document.getElementById("status");
    
    btn.onclick = () => {
        const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!Recognition) { status.innerText = "Nicht unterstützt."; return; }
        
        const rec = new Recognition();
        rec.lang = 'de-DE';
        
        rec.onstart = () => { 
            status.innerText = "🔴 Höre zu..."; 
            btn.style.backgroundColor = "#ffcccc"; 
        };
        
        rec.onresult = e => {
            const text = e.results[0][0].transcript;
            
            // 1. Wert an Streamlit senden
            window.parent.postMessage({
                type: 'streamlit:set_widget_value',
                data: {value: text, widgetId: 'speech_input_receiver'}
            }, '*');
            
            // 2. Streamlit zum Neuladen zwingen, damit handle_voice_input() auslöst
            setTimeout(() => {
                window.parent.postMessage({type: 'streamlit:set_page_config', data: {}}, '*');
            }, 100);
            
            status.innerText = "✅ Erkannt: " + text;
        };
        
        rec.onend = () => { btn.style.backgroundColor = "#f0f2f6"; };
        rec.start();
    };
    </script>
    """, height=100)

# --- 10. END SESSION ---
st.divider()
if not st.session_state.finished:
    if st.button("Beenden & Feedback", type="primary"):
        st.session_state.finished = True
        st.rerun()
else:
    st.header("Mentor Feedback")
    if "mentor_feedback" not in st.session_state:
        with st.spinner("Analysiere..."):
            chat_list = [m for m in st.session_state.chat_history if m["role"] != "system"]
            resp = client.chat.completions.create(model=model, messages=[
                {"role": "system", "content": mentor_instructions},
                {"role": "user", "content": str(chat_list)}
            ])
            st.session_state.mentor_feedback = resp.choices[0].message.content
    st.markdown(st.session_state.mentor_feedback)