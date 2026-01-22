import streamlit as st
from openai import OpenAI
import os
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

model = "gpt-4o"

st.set_page_config(page_title="SI Dialogue Lab", layout="centered")
st.title("SI Dialogue Lab")

# --- 1. HELP FUNCTION FOR AUTOMATIC RECOGNITION ---
def extract_role_label(text):
    """Extrahiert die Rolle (z.B. Mitarbeiterin) aus dem partner_de Block."""
    match = re.search(r"DU BIST (?:DIE|DER)\s+([A-ZÄÖÜa-zäöü]+)", text)
    if match:
        return match.group(1).strip()
    return "Gesprächspartner*in"

# 2. SETUP & DATA LOADING
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

# Load Scenario and parse metadata
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
    st.error(f"Szenario-Datei nicht gefunden.")
    st.stop()

if os.path.exists(analysis_path):
    with open(analysis_path, "r", encoding="utf-8") as f:
        mentor_instructions = f.read()
else:
    st.error(f"Analyse-Datei nicht gefunden.")
    st.stop()

st.subheader("Briefing für das Gespräch")
st.markdown(user_instruction)

# --- 3. INITIALIZATION ---
if "current_scenario" not in st.session_state or st.session_state.current_scenario != selected_scenario_name:
    warte_anweisung = "\n\nWARTE AUF START: Der User wird das Gespräch eröffnen. Reagiere dann direkt in deiner Rolle."
    namens_anweisung = "\nNAMENSWAHL: Wähle einen Namen für dich (z.B. Marc, Sarah), aber nenne ihn erst, wenn es passt."
    
    st.session_state.chat_history = [{"role": "system", "content": full_ki_logic + warte_anweisung + namens_anweisung}]
    st.session_state.finished = False
    st.session_state.current_scenario = selected_scenario_name
    st.rerun()

# Setup OpenAI Client
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# --- 4. START NOTE & CHAT DISPLAY ---
if len(st.session_state.chat_history) == 1:
    st.info("Der Raum ist bereit. Bitte eröffnen Sie das Gespräch über das Eingabefeld unten.")

for message in st.session_state.chat_history:
    if message["role"] != "system":
        label = "Du" if message["role"] == "user" else ai_display_name
        with st.chat_message(message["role"]):
            st.write(f"**{label}:** {message['content']}")

# --- 5. CHAT INPUT ---
if not st.session_state.get("finished", False):
    if user_input := st.chat_input("Schreiben Sie Ihre Antwort..."):
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        try:
            response = client.chat.completions.create(
                model=model,
                messages=st.session_state.chat_history
            )
            ai_answer = response.choices[0].message.content
            st.session_state.chat_history.append({"role": "assistant", "content": ai_answer})
        except Exception as e:
            st.error(f"Fehler bei der Anfrage: {e}")
        st.rerun()

# --- 6. BUTTONS & ANALYSIS ---
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
    if "mentor_feedback" not in st.session_state:
        with st.spinner("Analysiere das Gespräch..."):
            chat_transcript = [m for m in st.session_state.chat_history if m["role"] != "system"]
            mentor_request = [
                {"role": "system", "content": mentor_instructions},
                {"role": "system", "content": f"Gesprächsprotokoll: {str(chat_transcript)}"}
            ]
            try:
                resp = client.chat.completions.create(model=model, messages=mentor_request)
                st.session_state.mentor_feedback = resp.choices[0].message.content
            except Exception as e:
                st.error(f"Fehler: {e}")
    
    if "mentor_feedback" in st.session_state:
        st.markdown(st.session_state.mentor_feedback)
        if st.button("Neues Gespräch beginnen"):
            for key in ["chat_history", "finished", "mentor_feedback", "current_scenario"]:
                st.session_state.pop(key, None)
            st.rerun()
    
    if "mentor_feedback" in st.session_state:
        st.markdown(st.session_state.mentor_feedback)
        st.download_button(
            label="Feedback als .txt herunterladen",
            data=st.session_state.mentor_feedback,
            file_name=f"Feedback_{selected_scenario_name}.txt",
            mime="text/plain"
        )
