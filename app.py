import time
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
import os
import json, re
from dotenv import load_dotenv

# For STT via WebRTC
from streamlit_webrtc import webrtc_streamer, WebRtcMode, ClientSettings
import av
import whisper
import tempfile

# --- 1. INITIAL SETUP ---
load_dotenv()
model = "gpt-4o"

st.set_page_config(page_title="SI Dialogue Lab", layout="centered")
st.title("SI Dialogue Lab")

# --- 2. SESSION STATE INITIALIZATION ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "finished" not in st.session_state:
    st.session_state.finished = False
if "last_spoken" not in st.session_state:
    st.session_state.last_spoken = None

# --- 3. UTILITY FUNCTIONS ---
def extract_role_label(text):
    """Extracts character name from scenario prompt for UI labels."""
    match = re.search(r"DU BIST (?:DIE|DER)\s+([A-ZÄÖÜa-zäöü]+)", text)
    return match.group(1) if match else "Gesprächspartner*in"

def format_for_tts(text: str) -> str:
    """Prepares text for cleaner audio output."""
    text = re.sub(r"\n\s*[-•]\s*", ". ", text)
    text = re.sub(r"\n{2,}", ". ", text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def tts_browser(text):
    """Injects JS for browser-native Text-to-Speech."""
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

def process_ai_response(text):
    """Sends user input to OpenAI and updates history."""
    if text and not st.session_state.finished:
        st.session_state.chat_history.append({"role": "user", "content": text})
        with st.spinner("KI überlegt..."):
            response = client.chat.completions.create(model=model, messages=st.session_state.chat_history)
            ai_text = response.choices[0].message.content
            st.session_state.chat_history.append({"role": "assistant", "content": ai_text})
        st.rerun()

# --- 4. DATA LOADING & SCENARIO HANDLING ---
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

# --- 5. INITIALIZE CHAT ON SCENARIO CHANGE ---
if "current_scenario" not in st.session_state or st.session_state.current_scenario != selected_scenario_name:
    st.session_state.chat_history = [{"role": "system", "content": full_ki_logic + "\n\nAntworte direkt in deiner Rolle."}]
    st.session_state.finished = False
    st.session_state.last_spoken = None
    st.session_state.current_scenario = selected_scenario_name
    st.rerun()

# OpenAI Client
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# --- 5. SPEECH-TO-TEXT VIA WEBRTC ---
st.markdown("### 🎤 Spracheingabe (WebRTC)")

# Whisper-Modell laden
@st.cache_resource
def load_whisper_model():
    return whisper.load_model("small")  # small = guter Kompromiss zwischen Geschwindigkeit & Qualität

whisper_model = load_whisper_model()

def audio_callback(frame: av.AudioFrame):
    """Verarbeitet Audio-Frames und konvertiert in WAV für Whisper"""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
        frame.to_ndarray().tofile(tmpfile)
        tmpfile.flush()
        result = whisper_model.transcribe(tmpfile.name, language="de")
        text = result["text"].strip()
        if text:
            st.session_state["last_recognized_speech"] = text
    return frame

webrtc_streamer(
    key="speech-recorder",
    mode=WebRtcMode.RECVONLY,
    client_settings=ClientSettings(
        rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
        media_stream_constraints={"audio": True, "video": False},
    ),
    audio_receiver_size=1024,
    audio_frame_callback=audio_callback,
)

# Wenn neue Sprache erkannt wurde → direkt an Chat senden
if "last_recognized_speech" in st.session_state:
    captured_text = st.session_state.pop("last_recognized_speech")
    if captured_text:
        st.info(f"🎙 Erkannt: {captured_text}")
        process_ai_response(captured_text)

# --- 7. SIDEBAR ---
with st.sidebar:
    st.header("Audio Einstellungen")
    auto_speak = st.toggle("Antworten automatisch vorlesen", value=False)
    if st.button("Sprachausgabe stoppen", use_container_width=True):
        components.html("<script>window.speechSynthesis.cancel();</script>", height=0)
        st.rerun()

# --- 8. BRIEFING UI ---
st.subheader("Briefing für das Gespräch")
with st.status("📋 Aufgabenstellung & Szenario-Details", expanded=True, state="complete"):
    st.markdown(user_instruction)
    if st.button("🔊 Briefing vorlesen", key="read_briefing"):
        tts_browser(user_instruction)

# --- 9. CHAT DISPLAY ---
if len(st.session_state.chat_history) <= 1:
    st.info("**Bereit für das Gespräch.** Nutzen Sie das Mikrofon oder das Textfeld.")

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

# Auto-TTS logic
if auto_speak and len(st.session_state.chat_history) > 1:
    last_msg = st.session_state.chat_history[-1]
    if last_msg["role"] == "assistant" and st.session_state.last_spoken != last_msg["content"]:
        tts_browser(last_msg["content"])
        st.session_state.last_spoken = last_msg["content"]

# --- 10. INPUT SECTION ---
user_text = st.chat_input("Schreiben Sie Ihre Antwort...")
if user_text:
    process_ai_response(user_text)

st.markdown("### 🎤 Spracheingabe")
# JavaScript component that captures voice and sends it to the STT Receiver widget
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
        if (!Recognition) { 
            status.innerText = "❌ Browser nicht unterstützt."; 
            return; 
        }
        const rec = new Recognition();
        rec.lang = 'de-DE';
        rec.interimResults = false;
        
        rec.onstart = () => { 
            status.innerText = "🔴 Ich höre zu..."; 
            btn.style.backgroundColor = "#ffcccc"; 
        };
        
        rec.onresult = e => {
            const text = e.results[0][0].transcript;
            
            // 1. Set the value in the Streamlit widget (STT Receiver)
            window.parent.postMessage({
                type: 'streamlit:set_widget_value',
                data: {value: text, widgetId: 'speech_input_receiver'}
            }, '*');
            
            // 2. Force a rerun signal so Python detects the change immediately
            setTimeout(() => {
                window.parent.postMessage({
                    type: 'streamlit:set_page_config', 
                    data: {title: "SI Dialogue Lab"}
                }, '*');
            }, 300);
            
            status.innerText = "✅ Erkannt: " + text;
        };
        
        rec.onerror = e => { status.innerText = "❌ Fehler: " + e.error; };
        rec.onend = () => { btn.style.backgroundColor = "#f0f2f6"; };
        rec.start();
    };
    </script>
    """, height=100
)

# --- 11. END SESSION & ANALYSIS ---
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