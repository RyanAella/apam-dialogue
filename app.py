# =========================================================
# Imports
# =========================================================
import os
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

# Project utilities
from audio_utils import tts_browser, tts_browser_queued, stt_browser
from llm_utils import get_chat_response, get_mentor_feedback, transcribe_audio_via_groq

from scenario_utils import (
    get_scenarios,
    load_scenario_prompts,
    parse_meta_block,
    assemble_mentor_messages,
    extract_role_label,
)


# =========================================================
# Page config (MUST be first Streamlit command)
# =========================================================
st.set_page_config(
    page_title="Lab für Sozioinformatik: Gesprächstraining",
    layout="wide"  # change to "centered" if needed
)


# =========================================================
# App setup
# =========================================================
load_dotenv()
model = "gpt-4o"

st.title("Lab für Sozioinformatik: Gesprächstraining")


# =========================================================
# Session State Defaults
# =========================================================
defaults = {
    "chat_history": [],
    "finished": False,
    "current_scenario": None,
    "briefing_spoken": False,
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)


# =========================================================
# Sidebar
# =========================================================
with st.sidebar:
    st.header("Audio Einstellungen")

    st.subheader("Ausgabe (Hören)")
    auto_speak = st.toggle("Alles automatisch vorlesen", value=False)

    # Emergency stop button for all active browser speech synthesis
    if st.button("Alle Sprachausgaben stoppen", use_container_width=True):
        components.html(
            "<script>window.speechSynthesis.cancel();</script>",
            height=0,
        )
        st.rerun()


# =========================================================
# Scenario Selection
# =========================================================
SCENARIOS = get_scenarios(
    os.stat("scenarios").st_mtime
)

titles = [v["ui_title"] for v in SCENARIOS.values()]
selected_title = st.selectbox("Wähle ein Szenario:", titles)

scenario_key = next(
    k for k, v in SCENARIOS.items() if v["ui_title"] == selected_title
)


# =========================================================
# Scenario Change Handling
# =========================================================
if st.session_state.current_scenario != scenario_key:
    prompts = load_scenario_prompts(scenario_key)

    with open(SCENARIOS[scenario_key]["path"], "r", encoding="utf-8") as f:
        _, gui_instruction = parse_meta_block(f.read())

    st.session_state.chat_history = [
        {"role": "system", "content": prompts["system"]},
        {"role": "system", "content": prompts["partner"]},
    ]

    st.session_state.user_instruction = gui_instruction
    st.session_state.ai_display_name = extract_role_label(prompts["partner"])
    st.session_state.mentor_prompt = prompts["mentor"]

    st.session_state.finished = False
    st.session_state.current_scenario = scenario_key
    st.session_state.briefing_spoken = False
    st.session_state.pop("mentor_feedback", None)

    st.rerun()


# =========================================================
# Scenario Briefing (GUI ONLY)
# =========================================================
st.subheader("Briefing für das Gespräch")

with st.status("📋 Deine Aufgabenstellung & Szenario-Details", expanded=True, state="complete"):
    st.markdown(st.session_state.user_instruction)

if auto_speak and not st.session_state.briefing_spoken:
    tts_browser(st.session_state.user_instruction)
    st.session_state.briefing_spoken = True


# =========================================================
# Chat
# =========================================================
if not st.session_state.finished:
    # if user_input := st.chat_input(accept_audio=True, placeholder="Was möchtest du sagen?"):
    if user_input := st.chat_input("Was möchtest du sagen?"):
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        if auto_speak:
            tts_browser_queued(user_input)
        
        ai_answer = get_chat_response(model, st.session_state.chat_history)

        if ai_answer:
            st.session_state.chat_history.append({"role": "assistant", "content": ai_answer})
            if auto_speak:
                tts_browser_queued(ai_answer)


# =====================================================
# Chat display
# =====================================================
if len(st.session_state.chat_history) == 1:
    # st.info(f"**Bereit für das Gespräch.** Eröffnen Sie den Dialog, indem Sie unten eine Nachricht eingeben oder das Mikrofon nutzen.")
    st.info(f"**Bereit für das Gespräch.** Eröffnen Sie den Dialog, indem Sie unten eine Nachricht eingeben.")

is_dark_mode = st.get_option("theme.base") == "dark"

for msg in st.session_state.chat_history:
    if msg["role"] == "system":
        continue

    label = "Du" if msg["role"] == "user" else st.session_state.ai_display_name

    if msg["role"] == "user":
        bg_color = "#2A3E5B" if is_dark_mode else "#D1E8FF"
        text_color = "#FFFFFF" if is_dark_mode else "#000000"
    else:
        bg_color = "#3C3C3C" if is_dark_mode else "#F0F0F0"
        text_color = "#FFFFFF" if is_dark_mode else "#000000"

    st.markdown(
        f"""
        <div style='background-color:{bg_color}; color:{text_color};
                    padding:10px; border-radius:12px; margin-bottom:5px'>
            <b>{label}:</b> {msg['content']}
        </div>
        """,
        unsafe_allow_html=True
    )


# =====================================================
# Finish & Mentor Feedback
# =====================================================
st.divider()

if not st.session_state.finished:
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Gespräch zurücksetzen", use_container_width=True):
            st.session_state.chat_history = st.session_state.chat_history[:2]
            st.session_state.finished = False
            st.rerun()

    with col2:
        if st.button("Beenden & Feedback erhalten", type="primary", use_container_width=True):
            st.session_state.finished = True
            st.rerun()

else:
    # -------------------------------------------------
    # Mentor Feedback Section
    # -------------------------------------------------
    st.header("Mentor Feedback")
    
    # Generate plaintext transcript for export
    chat_transcript_text = "GESPRÄCHSPROTOKOLL\n" + "=" * 20 + "\n\n"

    for m in st.session_state.chat_history:
        if m["role"] == "system":
            continue

        label = (
            "Du"
            if m["role"] == "user"
            else st.session_state.ai_display_name
        )

        chat_transcript_text += f"{label}: {m['content']}\n\n"

    # Fetch AI analysis if not already stored
    if "mentor_feedback" not in st.session_state:
        with st.spinner("Analysiere das Gespräch..."):
            mentor_messages = assemble_mentor_messages(
                st.session_state.mentor_prompt,
                st.session_state.chat_history
            )

            feedback = get_mentor_feedback(
                model,
                mentor_messages
            )

            if feedback:
                st.session_state.mentor_feedback = feedback
                if auto_speak:
                    tts_browser(feedback)
    
    if "mentor_feedback" in st.session_state:
        st.markdown(st.session_state.mentor_feedback)
        
               # -------- Export --------
        full_export = (
            chat_transcript_text
            + "\n"
            + "=" * 20
            + "\nMENTOR FEEDBACK\n"
            + "=" * 20
            + "\n\n"
            + st.session_state.mentor_feedback
        )

        col_down1, col_down2 = st.columns(2)

        with col_down1:
            st.download_button(
                label="Protokoll & Feedback herunterladen",
                data=full_export,
                file_name=f"Dialog_Lab_{st.session_state.current_scenario}.txt",
                mime="text/plain",
                use_container_width=True
            )


        with col_down2:
            if st.button("Neues Gespräch beginnen", use_container_width=True):
                for key in [
                    "chat_history",
                    "finished",
                    "mentor_feedback",
                    "current_scenario",
                ]:
                    st.session_state.pop(key, None)
                st.rerun()
