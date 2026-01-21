import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

model = "gpt-4o"

st.set_page_config(page_title="SI Dialogue Lab", layout="centered")
st.title("SI Dialogue Lab")

# 1. SETUP & DATA LOADING
SCENARIOS = {
    "Verspätungen beim Reporting": {
        "scenario": "scenario_controlling.txt",
        "analysis": "analyze_controlling.txt"
    },
    "1. VP of Engineering – Strategic DEI Consulting Pitch": {
        "scenario": "scenario_1.txt",
        "analysis": "analyze.txt"
    }
}

selected_scenario_name = st.selectbox("Wählen Sie ein Szenario:", list(SCENARIOS.keys()))

selected_files = SCENARIOS[selected_scenario_name]
selected_scenario_file = selected_files["scenario"]
selected_analysis_file = selected_files["analysis"]

scenario_path = os.path.join("prompts", "scenarios", selected_scenario_file)
analysis_path = os.path.join("prompts", "analysis", selected_analysis_file)

# Load Scenario and parse metadata
if os.path.exists(scenario_path):
    with open(scenario_path, "r", encoding="utf-8") as f:
        raw_content = f.read()

    content_parts = raw_content.split("### SYSTEM PROMPT ###")
    # Alles vor ### SYSTEM PROMPT ### ist für den User
    user_instruction = content_parts[0].replace("### GUI INSTRUCTION ###", "").strip()
    # Alles danach ist das Regelwerk für die KI
    full_ki_logic = content_parts[1].strip() if len(content_parts) > 1 else raw_content
else:
    st.error(f"Szenario-Datei nicht gefunden.")
    st.stop()

# NEU: Dynamisches Laden der Analyse-Datei
if os.path.exists(analysis_path):
    with open(analysis_path, "r", encoding="utf-8") as f:
        mentor_instructions = f.read()
else:
    st.error(f"Analyse-Datei {selected_analysis_file} nicht gefunden.")
    st.stop()

st.subheader("Briefing für das Gespräch")
st.markdown(user_instruction)

# --- 2. INITIALIZATION (With Scenario Reset) ---
# If the scenario changes, we must wipe the history to trigger a new auto-start
if "current_scenario" not in st.session_state or st.session_state.current_scenario != selected_scenario_name:
    namens_anweisung = "\n\nNAMENSWAHL: Wähle zu Beginn einen Namen für dich (männlich oder weiblich, z.B. Marc, Thomas, Sarah oder Julia). Bleibe das gesamte Gespräch über bei diesem Namen."
    
    st.session_state.chat_history = [{"role": "system", "content": full_ki_logic + namens_anweisung}]
    st.session_state.finished = False
    st.session_state.current_scenario = selected_scenario_name
    st.rerun()

# Setup OpenAI Client
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# --- 3. DYNAMIC AUTO-START (The AI opens the meeting) ---
if len(st.session_state.chat_history) == 1:
    with st.spinner("Gesprächspartner:in tritt dem Raum bei..."):
        
        trigger_instruction = (
            "Lies deine Rollenbeschreibung oben genau. Beginne das Rollenspiel jetzt mit deinem ersten Satz. "
            "Wähle einen passenden Namen (männlich oder weiblich) für dich, aber nenne ihn NICHT sofort, "
            "es sei denn, die Situation erfordert eine förmliche Vorstellung. "
            "Reagiere stattdessen unmittelbar auf den Kontext des Szenarios (z.B. die aktuelle Arbeit, "
            "die Einladung zum Gespräch oder die Erwartungshaltung gegenüber deinem Gegenüber)."
        )

        trigger_prompt = st.session_state.chat_history + [
            {"role": "system", "content": trigger_instruction}
        ]

        response = client.chat.completions.create(
            model=model,
            messages=trigger_prompt,
            temperature=0.7 # Higher temperature for a more creative/natural opening
        )

        first_message = response.choices[0].message.content
        st.session_state.chat_history.append({"role": "assistant", "content": first_message})
        st.rerun()

# --- 4. DISPLAY CHAT ---
for message in st.session_state.chat_history:
    if message["role"] != "system":
        # Neutrales Label, da der Name ja im Text der KI vorkommt
        label = "Du" if message["role"] == "user" else "Gegenüber"
        with st.chat_message(message["role"]):
            st.write(f"**{label}:** {message['content']}")

# --- 5. CHAT INPUT ---
if not st.session_state.get("finished", False):
    # Wir nutzen ein neutrales Label oder fragen das Dictionary ab
    prompt_placeholder = "Schreiben Sie Ihre Antwort..."
    
    if user_input := st.chat_input(prompt_placeholder):
        # Nachricht zur Historie hinzufügen
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        # Der API-Aufruf erfolgt nun mit der gesamten Historie
        # (Inklusive des System-Prompts deiner Chefin am Anfang)
        try:
            response = client.chat.completions.create(
                model=model,
                messages=st.session_state.chat_history
            )
            ai_answer = response.choices[0].message.content
            st.session_state.chat_history.append({"role": "assistant", "content": ai_answer})
        except Exception as e:
            st.error(f"Fehler bei der Anfrage: {e}")
        
        # Seite neu laden, um die neue Antwort oben anzuzeigen
        st.rerun()

# --- 6. ANALYSIS & RESTART ---
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
    st.header("Mentor Feedback")
    
    if st.button("Neues Gespräch beginnen", use_container_width=True):
        for key in ["chat_history", "finished", "mentor_feedback", "current_scenario"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    if "mentor_feedback" not in st.session_state:
        with st.spinner("Analysiere das Gespräch..."):
            chat_transcript = [m for m in st.session_state.chat_history if m["role"] != "system"]
            
            mentor_request = [
                {"role": "system", "content": mentor_instructions},
                {"role": "system", "content": f"Hier ist das Gesprächsprotokoll: {str(chat_transcript)}"}
            ]

            try:
                resp = client.chat.completions.create(model=model, messages=mentor_request)
                st.session_state.mentor_feedback = resp.choices[0].message.content
            except Exception as e:
                st.error(f"Fehler bei der Analyse: {e}")
    
    if "mentor_feedback" in st.session_state:
        st.markdown(st.session_state.mentor_feedback)
        st.download_button(
            label="Feedback als .txt herunterladen",
            data=st.session_state.mentor_feedback,
            file_name=f"Feedback_{selected_scenario_name}.txt",
            mime="text/plain"
        )
