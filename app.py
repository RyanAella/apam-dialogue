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

# --- 2. SESSION STATE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "finished" not in st.session_state:
    st.session_state.finished = False

# --- 3. CORE LOGIC ---
def process_ai_response(text):
    """Verarbeitet User-Input und holt KI-Antwort."""
    if text and not st.session_state.finished:
        st.session_state.chat_history.append({"role": "user", "content": text})
        with st.spinner("KI überlegt..."):
            response = client.chat.completions.create(model=model, messages=st.session_state.chat_history)
            ai_text = response.choices[0].message.content
            st.session_state.chat_history.append({"role": "assistant", "content": ai_text})
        st.rerun()

# --- 4. STT BRIDGE (DER FIX) ---
# Das JavaScript schreibt in dieses Feld. 
# Wir nennen es "voice_bridge" und verstecken es (optional) per CSS.
voice_input = st.text_input("Spracheingabe Empfänger", key="voice_bridge")

if voice_input:
    # Sobald Text hier landet, verarbeiten wir ihn sofort
    captured_text = voice_input
    # Wir leeren den State manuell, damit das Feld für die nächste Eingabe bereit ist
    st.session_state.voice_bridge = "" 
    process_ai_response(captured_text)

# --- 5. SCENARIO SELECTION ---
SCENARIOS = {
    "Verspätungen beim Reporting": {"scenario": "scenario_reporting.txt", "analysis": "analyze_reporting.txt"},
    "Frühzeitiges Melden bei Schwierigkeiten": {"scenario": "scenario_difficulties.txt", "analysis": "analyze_difficulties.txt"}
}

selected_scenario_name = st.selectbox("Wählen Sie ein Szenario:", list(SCENARIOS.keys()))
selected_files = SCENARIOS[selected_scenario_name]

# Laden der Prompts
scenario_path = os.path.join("prompts", "scenarios", selected_files["scenario"])
if os.path.exists(scenario_path):
    with open(scenario_path, "r", encoding="utf-8") as f:
        raw_content = f.read()
    
    # AI Name finden
    match = re.search(r"DU BIST (?:DIE|DER)\s+([A-ZÄÖÜa-zäöü]+)", raw_content)
    ai_display_name = match.group(1) if match else "Gesprächspartner*in"
    
    parts = raw_content.split("### SYSTEM PROMPT ###")
    user_instruction = parts[0].replace("### GUI INSTRUCTION ###", "").strip()
    system_logic = parts[1].strip() if len(parts) > 1 else raw_content
else:
    st.error("Datei nicht gefunden.")
    st.stop()

# Chat-Initialisierung bei Szenario-Wechsel
if "current_scenario" not in st.session_state or st.session_state.current_scenario != selected_scenario_name:
    st.session_state.chat_history = [{"role": "system", "content": system_logic}]
    st.session_state.current_scenario = selected_scenario_name
    st.rerun()

# --- 6. UI ---
st.info(user_instruction)

for msg in st.session_state.chat_history:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(f"**{'Du' if msg['role'] == 'user' else ai_display_name}:** {msg['content']}")

# --- 7. MIKROFON KOMPONENTE (DER STABILE WEG) ---
st.markdown("### 🎤 Spracheingabe")
components.html(f"""
    <script>
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new Recognition();
    rec.lang = 'de-DE';

    function sendToStreamlit(text) {{
        // Suche das Textfeld im Streamlit-Parent-Fenster
        const inputs = window.parent.document.querySelectorAll('input[type="text"]');
        let target = null;
        for (let i of inputs) {{
            if (i.ariaLabel === "Spracheingabe Empfänger") {{
                target = i;
                break;
            }}
        }}

        if (target) {{
            target.value = text;
            // Wichtig: Diese Events lösen den Rerun in Python aus
            target.dispatchEvent(new Event('input', {{ bubbles: true }}));
            target.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
    }}

    rec.onresult = (e) => {{
        const text = e.results[0][0].transcript;
        sendToStreamlit(text);
    }};

    document.body.innerHTML = `
        <button id="m" style="width:100%; padding:15px; background:#FF4B4B; color:white; border:none; border-radius:10px; cursor:pointer; font-weight:bold;">
            🎤 KLICKEN & SPRECHEN
        </button>
    `;

    document.getElementById('m').onclick = () => {{
        rec.start();
        document.getElementById('m').innerText = "🔴 Höre zu...";
    }};
    
    rec.onend = () => {{
        document.getElementById('m').innerText = "🎤 KLICKEN & SPRECHEN";
    }};
    </script>
""", height=70)

# --- 8. ANALYSIS & FEEDBACK ---
st.divider()
if not st.session_state.finished:
    if st.button("Beenden & Feedback", type="primary"):
        st.session_state.finished = True
        st.rerun()
else:
    st.header("Mentor Feedback")
    if "mentor_feedback" not in st.session_state:
        with st.spinner("Analysiere Gespräch..."):
            chat_list = [m for m in st.session_state.chat_history if m["role"] != "system"]
            mentor_request = [{"role": "system", "content": mentor_instructions}, {"role": "user", "content": str(chat_list)}]
            resp = client.chat.completions.create(model=model, messages=mentor_request)
            st.session_state.mentor_feedback = resp.choices[0].message.content
    st.markdown(st.session_state.mentor_feedback)
    if st.button("Neues Gespräch starten"):
        for k in ["chat_history", "finished", "mentor_feedback", "current_scenario"]:
            st.session_state.pop(k, None)
        st.rerun()