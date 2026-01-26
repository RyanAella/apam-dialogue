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

# CSS to hide the hidden STT receiver input field completely
st.markdown("""
    <style>
    div[data-testid="stTextInput"]:has(input[aria-label="STT Receiver"]) {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "finished" not in st.session_state:
    st.session_state.finished = False
if "last_spoken" not in st.session_state:
    st.session_state.last_spoken = None

# --- UTILITY FUNCTIONS ---
def extract_role_label(text):
    """Extracts the character name from the scenario prompt for GUI labeling."""
    match = re.search(r"DU BIST (?:DIE|DER)\s+([A-ZÄÖÜa-zäöü]+)", text)
    return match.group(1) if match else "Gesprächspartner*in"

def format_for_tts(text: str) -> str:
    """Cleans text for better Text-to-Speech flow."""
    text = re.sub(r"\n\s*[-•]\s*", ". ", text)
    text = re.sub(r"\n{2,}", ". ", text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def tts_browser(text):
    """Uses Web Speech API to read text via Javascript injection."""
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

# --- DATA LOADING & SCENARIO HANDLING ---
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

scenario_path = os.path.join("prompts", "scenarios", selected_files["scenario"])
analysis_path = os.path.join("prompts", "analysis", selected_files["analysis"])

if os.path.exists(scenario_path):
    with open(scenario_path, "r", encoding="utf-8") as f:
        raw_content = f.read()

    if "partner_de =" in raw_content:
        role_part = raw_content.split("partner_de =")[1]
        ai_display_name = extract_role_label(role_part)
    else:
        ai_display_name = "Gesprächspartner*in"

    content_parts = raw_content.split("### SYSTEM PROMPT ###")
    user_instruction = content_parts[0].replace("### GUI INSTRUCTION ###", "").strip()
    full_ki_logic = content_parts[1].strip() if len(content_parts) > 1 else raw_content
else:
    st.error("Szenario-Datei nicht gefunden.")
    st.stop()

if os.path.exists(analysis_path):
    with open(analysis_path, "r", encoding="utf-8") as f:
        mentor_instructions = f.read()

# --- SIDEBAR: AUDIO CONTROLS ---
with st.sidebar:
    st.header("Audio Einstellungen")
    auto_speak = st.toggle("Antworten automatisch vorlesen", value=False)
    if st.button("Sprachausgabe stoppen", use_container_width=True):
        components.html("<script>window.speechSynthesis.cancel();</script>", height=0)
        st.rerun()

# --- BRIEFING UI ---
st.subheader("Briefing für das Gespräch")
with st.status("📋 Aufgabenstellung & Szenario-Details", expanded=True, state="complete"):
    st.markdown(user_instruction)
    if st.button("🔊 Briefing vorlesen", key="read_briefing"):
        tts_browser(user_instruction)

# --- SESSION RESET LOGIC ---
if "current_scenario" not in st.session_state or st.session_state.current_scenario != selected_scenario_name:
    st.session_state.chat_history = [{"role": "system", "content": full_ki_logic + "\n\nAntworte direkt in deiner Rolle."}]
    st.session_state.finished = False
    st.session_state.last_spoken = None
    st.session_state.current_scenario = selected_scenario_name
    st.rerun()

# OpenAI Client Setup
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# --- PROCESS VOICE/TEXT INPUT ---
def process_ai_response(text):
    """Central function to handle AI generation after user input."""
    if text and not st.session_state.finished:
        st.session_state.chat_history.append({"role": "user", "content": text})
        with st.spinner("KI überlegt..."):
            response = client.chat.completions.create(model=model, messages=st.session_state.chat_history)
            ai_text = response.choices[0].message.content
            st.session_state.chat_history.append({"role": "assistant", "content": ai_text})
        st.rerun()

# Receiver field (hidden via CSS)
speech_capture = st.text_input("STT Receiver", key="speech_input_receiver", label_visibility="collapsed")

# Trigger processing if voice input is detected
if speech_capture:
    input_text = speech_capture
    st.session_state["speech_input_receiver"] = "" # Reset immediately
    process_ai_response(input_text)

# --- CHAT DISPLAY ---
if len(st.session_state.chat_history) <= 1:
    st.info("**Bereit für das Gespräch.** Tippen Sie unten oder nutzen Sie das Mikrofon.")

for i, message in enumerate(st.session_state.chat_history):
    if message["role"] != "system":
        is_user = message["role"] == "user"
        label = "Du" if is_user else ai_display_name
        avatar = "👤" if is_user else "👩‍💼" 
        with st.chat_message(message["role"], avatar=avatar):
            st.write(f"**{label}:** {message['content']}")
            if not is_user:
                if st.button("Vorlesen", key=f"btn_{i}"):
                    tts_browser(message['content'])

if auto_speak and len(st.session_state.chat_history) > 1:
    last_msg = st.session_state.chat_history[-1]
    if last_msg["role"] == "assistant" and st.session_state.last_spoken != last_msg["content"]:
        tts_browser(last_msg["content"])
        st.session_state.last_spoken = last_msg["content"]

# --- INPUT SECTION ---
user_input = st.chat_input("Schreiben Sie Ihre Antwort...")
if user_input:
    process_ai_response(user_input)

st.markdown("### 🎤 Spracheingabe")
components.html(
    """
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
        if (!Recognition) { alert("Browser nicht unterstützt."); return; }
        const rec = new Recognition();
        rec.lang = 'de-DE';
        rec.onstart = () => { status.innerText = "🔴 Ich höre zu..."; btn.style.backgroundColor = "#ffcccc"; };
        rec.onresult = e => {
            const text = e.results[0][0].transcript;
            window.parent.postMessage({type: 'streamlit:set_widget_value', data: {value: text, widgetId: 'speech_input_receiver'}}, '*');
            setTimeout(() => { window.parent.postMessage({type: 'streamlit:set_page_config', data: {}}, '*'); }, 200);
            status.innerText = "✅ Erkannt: " + text;
        };
        rec.onend = () => { btn.style.backgroundColor = "#f0f2f6"; };
        rec.start();
    };
    </script>
    """, height=80
)

# --- END SESSION & ANALYSIS ---
st.divider()
if not st.session_state.finished:
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Gespräch zurücksetzen", use_container_width=True):
            st.session_state.chat_history = []; st.rerun()
    with c2:
        if st.button("Beenden & Feedback", type="primary", use_container_width=True):
            st.session_state.finished = True; st.rerun()
else:
    st.header("Mentor Feedback")
    if "mentor_feedback" not in st.session_state:
        with st.spinner("Analysiere..."):
            chat_list = [m for m in st.session_state.chat_history if m["role"] != "system"]
            mentor_request = [{"role": "system", "content": mentor_instructions}, {"role": "user", "content": str(chat_list)}]
            resp = client.chat.completions.create(model=model, messages=mentor_request)
            st.session_state.mentor_feedback = resp.choices[0].message.content
    st.markdown(st.session_state.mentor_feedback)
    if st.button("Neues Gespräch"):
        for k in ["chat_history", "finished", "mentor_feedback", "current_scenario"]: st.session_state.pop(k, None)
        st.rerun()