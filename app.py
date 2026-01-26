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

# --- 2. SESSION STATE INITIALIZATION ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "finished" not in st.session_state:
    st.session_state.finished = False
if "last_spoken" not in st.session_state:
    st.session_state.last_spoken = None

# --- 3. CORE LOGIC ---
def process_ai_response(text):
    """Sends user input to OpenAI and updates history."""
    if text and not st.session_state.finished:
        st.session_state.chat_history.append({"role": "user", "content": text})
        with st.spinner("KI überlegt..."):
            response = client.chat.completions.create(model=model, messages=st.session_state.chat_history)
            ai_text = response.choices[0].message.content
            st.session_state.chat_history.append({"role": "assistant", "content": ai_text})
        st.rerun()

# --- 4. DATA LOADING ---
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

# Paths for prompts
scenario_path = os.path.join("prompts", "scenarios", selected_files["scenario"])
analysis_path = os.path.join("prompts", "analysis", selected_files["analysis"])

if os.path.exists(scenario_path):
    with open(scenario_path, "r", encoding="utf-8") as f:
        raw_content = f.read()
    
    # Extract AI name
    match = re.search(r"DU BIST (?:DIE|DER)\s+([A-ZÄÖÜa-zäöü]+)", raw_content)
    ai_display_name = match.group(1) if match else "Gesprächspartner*in"
    
    content_parts = raw_content.split("### SYSTEM PROMPT ###")
    user_instruction = content_parts[0].replace("### GUI INSTRUCTION ###", "").strip()
    full_ki_logic = content_parts[1].strip() if len(content_parts) > 1 else raw_content
else:
    st.error("Szenario-Datei nicht gefunden.")
    st.stop()

if os.path.exists(analysis_path):
    with open(analysis_path, "r", encoding="utf-8") as f:
        mentor_instructions = f.read()

# Reset session on scenario change
if "current_scenario" not in st.session_state or st.session_state.current_scenario != selected_scenario_name:
    st.session_state.chat_history = [{"role": "system", "content": full_ki_logic + "\n\nAntworte direkt in deiner Rolle."}]
    st.session_state.finished = False
    st.session_state.last_spoken = None
    st.session_state.current_scenario = selected_scenario_name
    st.rerun()

# --- 5. STT BRIDGE (The fix for starting the dialogue) ---
# This field receives the text from JavaScript
voice_input = st.text_input("Spracheingabe Empfänger", key="voice_bridge", label_visibility="collapsed")

if voice_input:
    # Immediately process and clear
    captured_text = voice_input
    st.session_state.voice_bridge = "" # Reset for next input
    process_ai_response(captured_text)

# --- 6. UI: BRIEFING & CHAT ---
st.subheader("Briefing für das Gespräch")
with st.status("📋 Aufgabenstellung & Szenario-Details", expanded=True):
    st.markdown(user_instruction)

for i, message in enumerate(st.session_state.chat_history):
    if message["role"] != "system":
        is_user = message["role"] == "user"
        with st.chat_message(message["role"], avatar="👤" if is_user else "👩‍💼"):
            st.write(f"**{'Du' if is_user else ai_display_name}:** {message['content']}")

# Text Input Fallback
user_text = st.chat_input("Schreiben Sie Ihre Antwort...")
if user_text:
    process_ai_response(user_text)

# --- 7. THE ROBUST MIC BUTTON ---
st.markdown("### 🎤 Spracheingabe")
components.html(f"""
    <script>
    function sendToStreamlit(text) {{
        const inputs = window.parent.document.querySelectorAll('input[type="text"]');
        let bridgeInput = null;
        for (let input of inputs) {{
            if (input.ariaLabel === "Spracheingabe Empfänger") {{
                bridgeInput = input;
                break;
            }}
        }}
        if (bridgeInput) {{
            bridgeInput.value = text;
            bridgeInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
            bridgeInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
    }}

    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {{
        document.body.innerHTML = "Browser STT nicht unterstützt.";
    }} else {{
        const rec = new Recognition();
        rec.lang = 'de-DE';
        rec.onresult = (e) => {{
            const text = e.results[0][0].transcript;
            sendToStreamlit(text);
        }};

        document.body.innerHTML = `
            <button id="btn" style="width:100%; padding:15px; background: #FF4B4B; color:white; border:none; border-radius:10px; cursor:pointer; font-weight:bold;">
                🎤 JETZT SPRECHEN
            </button>
        `;

        document.getElementById('btn').onclick = () => {{
            rec.start();
            document.getElementById('btn').innerText = "🔴 Höre zu...";
            document.getElementById('btn').style.background = "#ff7272";
        }};
        
        rec.onend = () => {{
            document.getElementById('btn').innerText = "🎤 JETZT SPRECHEN";
            document.getElementById('btn').style.background = "#FF4B4B";
        }};
    }}
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