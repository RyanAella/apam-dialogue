import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

st.set_page_config(page_title="SI Dialogue Lab", layout="centered")
st.title("SI Dialogue Lab")

# 1. SETUP & DATA LOADING
SCENARIOS = {
    "1. VP of Engineering – Strategic DEI Consulting Pitch": "scenario_1.txt",
    # Add other scenarios here
}

selected_scenario_name = st.selectbox("Choose a scenario:", list(SCENARIOS.keys()))
selected_filename = SCENARIOS[selected_scenario_name]
scenario_path = os.path.join("prompts", "scenarios", selected_filename)

# Load Scenario and parse metadata
if os.path.exists(scenario_path):
    with open(scenario_path, "r", encoding="utf-8") as f:
        raw_content = f.read()
    
    parts = raw_content.split("---", 1)
    header = parts[0]
    full_scenario = parts[1] if len(parts) > 1 else raw_content

    # Extract dynamic name
    ai_name = "The Partner"
    for line in header.split("\n"):
        if line.startswith("NAME:"):
            ai_name = line.replace("NAME:", "").strip()
else:
    st.error(f"File {selected_filename} not found.")
    st.stop()

with open("prompts/analyze.txt", "r", encoding="utf-8") as f:
    mentor_instructions = f.read()

# --- 2. INITIALIZATION (With Scenario Reset) ---
# If the scenario changes, we must wipe the history to trigger a new auto-start
if "current_scenario" not in st.session_state or st.session_state.current_scenario != selected_scenario_name:
    st.session_state.chat_history = [{"role": "system", "content": full_scenario}]
    st.session_state.finished = False
    st.session_state.current_scenario = selected_scenario_name
    st.session_state.ai_name = ai_name
    # Clear old feedback when switching scenarios
    if "mentor_feedback" in st.session_state:
        del st.session_state.mentor_feedback
    st.rerun()

# Setup OpenAI Client
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# --- 3. DYNAMIC AUTO-START (The AI opens the meeting) ---
if len(st.session_state.chat_history) == 1:
    with st.spinner(f"{st.session_state.ai_name} is preparing the meeting..."):
        # We append a temporary "trigger" instruction to get a strong opening
        trigger_prompt = st.session_state.chat_history + [
            {"role": "system", "content": f"You are {st.session_state.ai_name}. Start the meeting now. Be direct, perhaps a bit skeptical or impatient, and set the tone. Do not greet with 'Hello, how can I help you?'. Instead, start with a statement about your situation or a direct challenge to the consultant."}
        ]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=trigger_prompt,
            temperature=0.8 # Higher temperature for a more creative/natural opening
        )
        first_message = response.choices[0].message.content
        st.session_state.chat_history.append({"role": "assistant", "content": first_message})
        st.rerun()

# --- 4. DISPLAY CHAT ---
for message in st.session_state.chat_history:
    if message["role"] != "system":
        label = "You" if message["role"] == "user" else st.session_state.ai_name
        with st.chat_message(message["role"]):
            st.write(f"**{label}:** {message['content']}")

# --- 5. CHAT INPUT ---
if not st.session_state.get("finished", False):
    if user_input := st.chat_input(f"Your reply to {st.session_state.ai_name}..."):
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        # Display user message immediately
        with st.chat_message("user"):
            st.write(f"**You:** {user_input}")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=st.session_state.chat_history
        )
        ai_answer = response.choices[0].message.content
        st.session_state.chat_history.append({"role": "assistant", "content": ai_answer})
        st.rerun()

# --- 6. ANALYSIS & RESTART ---
st.divider()
is_finished = st.session_state.get("finished", False)

if not is_finished:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Reset Conversation", use_container_width=True):
            del st.session_state.chat_history
            st.rerun()
    with col2:
        if st.button("End & Get Feedback", type="primary", use_container_width=True):
            st.session_state.finished = True
            st.rerun()
else:
    st.header("Mentor Feedback")
    
    if st.button("Start New Session"):
        keys_to_clear = ["chat_history", "finished", "mentor_feedback"]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    if "mentor_feedback" not in st.session_state:
        with st.spinner("Analyzing performance..."):
            mentor_request = [
                {"role": "system", "content": mentor_instructions},
                {"role": "system", "content": f"Transcript: {str(st.session_state.chat_history)}"}
            ]
            resp = client.chat.completions.create(model="gpt-4o-mini", messages=mentor_request)
            st.session_state.mentor_feedback = resp.choices[0].message.content
    
    st.info(st.session_state.mentor_feedback)
    st.download_button("Download Feedback", st.session_state.mentor_feedback, file_name="feedback.txt")
    