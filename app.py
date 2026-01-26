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

# CSS to hide the hidden STT receiver input field
st.markdown("""
    <style>
    div[data-testid="stTextInput"]:has(input[aria-label="STT Receiver"]) {
        height: 0px;
        margin-bottom: -70px;
        opacity: 0;
        pointer-events: none;
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

# Hidden input field to receive text from the Browser Speech API
st.text_input("STT Receiver", key="speech_input_receiver", label_visibility="collapsed")

# --- 1. SIDEBAR: CENTRAL AUDIO CONTROLS ---
with st.sidebar:
    st.header("Audio Settings")
    auto_speak = st.toggle("Read responses automatically", value=False)

    if st.button("Stop all speech output", use_container_width=True):
        components.html("<script>window.speechSynthesis.cancel();</script>", height=0)
        st.rerun()

# --- 1a UTILITY FUNCTIONS ---
def extract_role_label(text):
    """Extracts the character name from the scenario prompt for GUI labeling."""
    match = re.search(r"DU BIST (?:DIE|DER)\s+([A-ZÄÖÜa-zäöü]+)", text)
    return match.group(1) if match else "Partner"

def format_for_tts(text: str) -> str:
    """Cleans text for better Text-to-Speech flow."""
    text = re.sub(r"\n\s*[-•]\s*", ". ", text) # Lists to sentences
    text = re.sub(r"\n{2,}", ". ", text)      # Double breaks to pauses
    text = text.replace("\n", " ")            # Single breaks to space
    text = re.sub(r"\s+", " ", text)          # Normalize whitespace
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

selected_scenario_name = st.selectbox("Select a scenario:", list(SCENARIOS.keys()))
selected_files = SCENARIOS[selected_scenario_name]

# Pathing for scenario and analysis prompt files
scenario_path = os.path.join("prompts", "scenarios", selected_files["scenario"])
analysis_path = os.path.join("prompts", "analysis", selected_files["analysis"])

if os.path.exists(scenario_path):
    with open(scenario_path, "r", encoding="utf-8") as f:
        raw_content = f.read()

    # Parse character name and split system prompt
    if "partner_de =" in raw_content:
        role_part = raw_content.split("partner_de =")[1]
        ai_display_name = extract_role_label(role_part)
    else:
        ai_display_name = "Partner"

    content_parts = raw_content.split("### SYSTEM PROMPT ###")
    user_instruction = content_parts[0].replace("### GUI INSTRUCTION ###", "").strip()
    full_ki_logic = content_parts[1].strip() if len(content_parts) > 1 else raw_content
else:
    st.error(f"Scenario file not found.")
    st.stop()

if os.path.exists(analysis_path):
    with open(analysis_path, "r", encoding="utf-8") as f:
        mentor_instructions = f.read()
else:
    st.error(f"Analysis file not found.")
    st.stop()

# --- BRIEFING UI SECTION ---
st.subheader("Briefing")
with st.status("📋 Task & Scenario Details", expanded=True, state="complete"):
    st.markdown(user_instruction)
    if st.button("🔊 Read briefing", key="read_briefing"):
        tts_browser(user_instruction)

# --- 3. SESSION STATE LOGIC & SCENARIO RESET ---
if "current_scenario" not in st.session_state or st.session_state.current_scenario != selected_scenario_name:
    wait_instruction = "\n\nWAIT FOR START: The user will open the conversation. React directly in your role."
    st.session_state.chat_history = [{"role": "system", "content": full_ki_logic + wait_instruction}]
    st.session_state.finished = False
    st.session_state.last_spoken = None
    st.session_state.current_scenario = selected_scenario_name
    st.rerun()

# OpenAI Client Setup
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# --- LOGIC: PROCESS SPEECH INPUT ---
# We check the session state directly because the widget value update triggers a rerun
current_speech = st.session_state.get("speech_input_receiver", "")

if current_speech and not st.session_state.finished:
    # 1. Add user message to history
    st.session_state.chat_history.append({"role": "user", "content": current_speech})
    # 2. Clear receiver field in state to prevent loops
    st.session_state["speech_input_receiver"] = ""
    # 3. Generate AI Response
    with st.spinner("Thinking..."):
        response = client.chat.completions.create(model=model, messages=st.session_state.chat_history)
        ai_text = response.choices[0].message.content
        st.session_state.chat_history.append({"role": "assistant", "content": ai_text})
    st.rerun()

# --- 4. CHAT DISPLAY & AUTO-VOICE ---
if len(st.session_state.chat_history) == 1:
    st.info(f"**Ready for conversation.** Start by typing below or using the microphone.")

for i, message in enumerate(st.session_state.chat_history):
    if message["role"] != "system":
        is_user = message["role"] == "user"
        label = "You" if is_user else ai_display_name
        avatar = "👤" if is_user else "👩‍💼" 
        
        with st.chat_message(message["role"], avatar=avatar):
            st.write(f"**{label}:** {message['content']}")
            if not is_user:
                if st.button(f"Read aloud", key=f"btn_{i}"):
                    tts_browser(message['content'])

# Handle automatic Text-to-Speech
if auto_speak and len(st.session_state.chat_history) > 1:
    last_msg = st.session_state.chat_history[-1]
    if last_msg["role"] == "assistant" and st.session_state.last_spoken != last_msg["content"]:
        tts_browser(last_msg["content"])
        st.session_state.last_spoken = last_msg["content"]

# --- CHAT INPUT ---
user_input = st.chat_input("Write your message...")

# --- 🎤 VOICE INPUT (BROWSER SPEECH API) ---
st.markdown("### 🎤 Voice Input")
components.html(
    """
    <div style="display:flex; align-items:center; gap:10px;">
      <button id="micBtn" style="
        font-size:16px; padding:10px 16px; border-radius:8px;
        cursor:pointer; background-color:#f0f2f6; border:1px solid #ddd;
      ">
        🎤 Start Speaking
      </button>
      <span id="status" style="font-family:sans-serif; font-size:13px; color:#555;">Ready.</span>
    </div>

    <script>
    const btn = document.getElementById("micBtn");
    const status = document.getElementById("status");

    btn.onclick = () => {
        const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!Recognition) {
            status.innerText = "❌ Browser not supported.";
            alert("This browser does not support Web Speech API. Please use Chrome or Edge.");
            return;
        }

        const rec = new Recognition();
        rec.lang = 'de-DE';
        rec.onstart = () => { 
            status.innerText = "🔴 Listening..."; 
            btn.style.backgroundColor = "#ffcccc";
        };

        rec.onresult = e => {
            const text = e.results[0][0].transcript;
            // Send text to Streamlit hidden widget
            window.parent.postMessage({
                type: 'streamlit:set_widget_value',
                data: { value: text, widgetId: 'speech_input_receiver' }
            }, '*');
            
            // Trigger a rerun signal
            setTimeout(() => {
                window.parent.postMessage({type: 'streamlit:set_page_config', data: {}}, '*');
            }, 150);
            
            status.innerText = "✅ Recognized: " + text;
        };

        rec.onend = () => {
            btn.style.backgroundColor = "#f0f2f6";
        };
        rec.start();
    };
    </script>
    """,
    height=80
)

# --- OPENAI CALL (FOR TEXT INPUT) ---
if user_input and not st.session_state.finished:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    response = client.chat.completions.create(model=model, messages=st.session_state.chat_history)
    ai_text = response.choices[0].message.content
    st.session_state.chat_history.append({"role": "assistant", "content": ai_text})
    st.rerun()

# --- 6. END SESSION & ANALYSIS ---
st.divider()
is_finished = st.session_state.get("finished", False)

if not is_finished:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Reset Conversation", use_container_width=True):
            del st.session_state.chat_history
            st.rerun()
    with col2:
        if st.button("Finish & Get Feedback", type="primary", use_container_width=True):
            st.session_state.finished = True
            st.rerun()
else:
    # --- MENTOR FEEDBACK SECTION ---
    st.header("Mentor Feedback")
    if "mentor_feedback" not in st.session_state:
        with st.spinner("Analyzing conversation..."):
            chat_transcript_list = [m for m in st.session_state.chat_history if m["role"] != "system"]
            mentor_request = [
                {"role": "system", "content": mentor_instructions},
                {"role": "system", "content": f"Transcript: {str(chat_transcript_list)}"}
            ]
            try:
                resp = client.chat.completions.create(model=model, messages=mentor_request)
                st.session_state.mentor_feedback = resp.choices[0].message.content
            except Exception as e:
                st.error(f"Error: {e}")
    
    if "mentor_feedback" in st.session_state:
        st.markdown(st.session_state.mentor_feedback)
        
        # Prepare export
        full_export = "TRANSCRIPT\n" + "="*20 + "\n"
        for m in st.session_state.chat_history:
             if m["role"] != "system":
                 full_export += f"{m['role']}: {m['content']}\n\n"
        full_export += "\nFEEDBACK\n" + "="*20 + "\n" + st.session_state.mentor_feedback
        
        col_down1, col_down2 = st.columns(2)
        with col_down1:
            st.download_button("Download Report", data=full_export, file_name="Feedback.txt", use_container_width=True)
        with col_down2:
            if st.button("Start New Conversation", use_container_width=True):
                for key in ["chat_history", "finished", "mentor_feedback", "current_scenario"]:
                    st.session_state.pop(key, None)
                st.rerun()