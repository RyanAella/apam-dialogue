import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# 1. SETUP & DATA LOADING
# with open("prompts/roleplay.txt", "r", encoding="utf-8") as f:
#     full_scenario = f.read()
prompt_files = [f for f in os.listdir("prompts/scenarios") if f.endswith(".txt")]
selected_prompt = st.selectbox(
    "Choose a scenario:",
    [
        "1. VP of Engineering – Strategic DEI Consulting Pitch",
    ]
)

with open(os.path.join("prompts/scenarios", selected_prompt), "r", encoding="utf-8") as f:
     full_scenario = f.read()

with open("prompts/analyze.txt", "r", encoding="utf-8") as f:
    mentor_instructions = f.read()

# 1. Setup OpenAI Client
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("OPENAI_API_KEY not found! Check your .env file.")
    st.stop()
client = OpenAI(api_key=api_key)

st.title("SI Dialogue Lab")

# 2. INITIALIZATION (The Safe)
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "system", "content": full_scenario}]
    st.session_state.finished = False

# 3. AUTO-START (Marc speaks first)
if len(st.session_state.chat_history) == 1:
    with st.spinner("Marc is entering the room..."):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=st.session_state.chat_history
        )
        first_message = response.choices[0].message.content
        st.session_state.chat_history.append({"role": "assistant", "content": first_message})
        st.rerun()

# 4. DISPLAY CHAT
for message in st.session_state.chat_history:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.write(message["content"])

# 5. CHAT INPUT (Only if not finished)
if not st.session_state.get("finished", False):
    if user_input := st.chat_input("Your reply to Marc..."):
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.chat_message("user"):
            st.write(user_input)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=st.session_state.chat_history
        )
        ai_answer = response.choices[0].message.content
        st.session_state.chat_history.append({"role": "assistant", "content": ai_answer})
        st.rerun()

# --- 6. THE FINALE: ANALYSIS MODE ---
st.divider()

# Check the state safely
is_finished = st.session_state.get("finished", False)

if not is_finished:
    # Button to end the session
    if st.button("End Conversation & Get Mentor Feedback"):
        st.session_state.finished = True
        st.rerun()
else:
    # WE ARE IN ANALYSIS MODE
    st.header("Mentor Feedback")
    
    # 1. IMMEDIATE RESTART (Place this ABOVE the analysis)
    if st.button("Restart Training"):
        keys_to_clear = ["chat_history", "finished", "mentor_feedback"]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun() # Stop everything and jump to the very top!

    # 2. ANALYSIS LOGIC (Only runs if we haven't just clicked Restart)
    if "chat_history" in st.session_state: 
        if "mentor_feedback" not in st.session_state:
            with st.spinner("Analyzing your conversation..."):
                mentor_request = [
                    {"role": "system", "content": mentor_instructions},
                    {"role": "system", "content": f"Transcript: {str(st.session_state.chat_history)}"}
                ]
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=mentor_request
                )
                st.session_state.mentor_feedback = response.choices[0].message.content
        
        # Display the result
        st.info(st.session_state.mentor_feedback)

        # --- DOWNLOAD FEEDBACK ---
        st.download_button(
            label="Download Analysis as TXT",
            data=st.session_state.mentor_feedback,
            file_name="DEI_Mentor_Feedback.txt",
            mime="text/plain"
        )