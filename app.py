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


def normalize_chat_input(chat_input):
    """
    Normalisiert Streamlit chat_input (Text / Audio / Mixed)
    zu einem reinen String für LLM-Verarbeitung.
    """
    if not chat_input:
        return None

    # Reiner Text
    if isinstance(chat_input, str):
        text = chat_input.strip()
        return text if text else None

    # Audio (Streamlit ChatInputValue)
    if hasattr(chat_input, "audio") and chat_input.audio:
        return transcribe_audio_via_groq(chat_input.audio)

    # Fallback: Textfeld bei Mixed Input
    text = getattr(chat_input, "text", "")
    text = text.strip()
    return text if text else None


# =========================================================
# Page config (MUST be first Streamlit command)
# =========================================================
st.set_page_config(
    page_title="Lab für Sozioinformatik: Gesprächstraining",
    layout="wide"  # change to "centered" if needed
)


# =========================================================
# Global UI Styling
# =========================================================
is_dark_mode = st.get_option("theme.base") == "dark"


sidebar_class = "dark" if is_dark_mode else "light"
st.markdown(f"""
<script>
const sidebar = document.querySelector('section[data-testid="stSidebar"]');
if (sidebar) {{
    sidebar.classList.add("{sidebar_class}");
}}
</script>
""", unsafe_allow_html=True)


sidebar_gradient = (
    "linear-gradient(180deg, #1E293B 0%, #111827 100%)"
    if is_dark_mode else
    "linear-gradient(180deg, #F8FAFC 0%, #E5E7EB 100%)"
)
sidebar_text_color = "#F8FAFC" if is_dark_mode else "#1F2937"
sidebar_border = "#2D3748" if is_dark_mode else "#CBD5E1"

main_surface = "#0B1220" if is_dark_mode else "#FFFFFF"
surface_border = "#1E293B" if is_dark_mode else "#E5E7EB"

primary_color = "#2563EB"

# Toggle / Checkbox / Radio
toggle_bg = "#1E293B" if is_dark_mode else "#E2E8F0"
toggle_text = "#F8FAFC" if is_dark_mode else "#1F2937"

st.markdown(f"""
<style>

/* ===== Sidebar ===== */
section[data-testid="stSidebar"].dark {{
    background: linear-gradient(180deg, #1E293B 0%, #111827 100%);
    border-right: 1px solid #2D3748;
}}

section[data-testid="stSidebar"].light {{
    background: linear-gradient(180deg, #F8FAFC 0%, #F1F5F9 100%);
    border-right: 1px solid #CBD5E1;
}}

/* Sidebar Container */
section[data-testid="stSidebar"] .block-container {{
    padding-top: 2rem;
    padding-bottom: 2rem;
}}

/* Textfarbe je Theme */
section[data-testid="stSidebar"].dark * {{
    color: #F8FAFC !important; /* hell auf dunkel */
}}

section[data-testid="stSidebar"].light * {{
    color: #1F2937 !important; /* dunkel auf hell */
}}
            
/* Selectbox moderner */
section[data-testid="stSidebar"].dark .stSelectbox div[data-baseweb="select"] {{
    background-color: #1E293B !important;
    border: 1px solid #2D3748 !important;
    color: #F8FAFC !important;
    border-radius: 8px;
}}

section[data-testid="stSidebar"].light .stSelectbox div[data-baseweb="select"] {{
    background-color: #E2E8F0 !important;
    border: 1px solid #CBD5E1 !important;
    color: #1F2937 !important;
    border-radius: 8px;
}}

/* ===== Main Surface ===== */
.main-surface {{
    background-color: {main_surface};
    padding: 2.5rem;
    border-radius: 18px;
    border: 1px solid {surface_border};
}}

/* ===== Chat Bubble ===== */
.chat-bubble {{
    padding: 12px 16px;
    border-radius: 18px;
    margin-bottom: 10px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    font-size: 0.95rem;
    line-height: 1.5;
}}

/* ===== Primary Button ===== */
button[kind="primary"] {{
    background-color: {primary_color} !important;
    color: #FFFFFF !important;
    border-radius: 10px !important;
    border: none !important;
}}

</style>
""", unsafe_allow_html=True)


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
    st.divider()

    SCENARIOS = get_scenarios(
        os.stat("scenarios").st_mtime
    )

    titles = [v["ui_title"] for v in SCENARIOS.values()]
    st.markdown("### 🎓 Wähle ein Szenario")

    selected_title = st.selectbox(
        label="",
        options=titles,
        label_visibility="collapsed"
    )

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
st.markdown("## Briefing")

with st.status("Deine Aufgabenstellung & Szenario-Details", expanded=True, state="complete"):
    st.markdown(st.session_state.user_instruction)

if auto_speak and not st.session_state.briefing_spoken:
    tts_browser(st.session_state.user_instruction)
    st.session_state.briefing_spoken = True


# =========================================================
# Chat
# =========================================================
if not st.session_state.finished:
    chat_input = st.chat_input(
        accept_audio=True,
        placeholder="Was möchtest du sagen?"
    )

    user_text = normalize_chat_input(chat_input)

    if user_text:
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_text
        })

        if auto_speak:
            tts_browser_queued(user_text)

        ai_answer = get_chat_response(
            model,
            st.session_state.chat_history
        )

        if ai_answer:
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": ai_answer
            })

            if auto_speak:
                tts_browser_queued(ai_answer)


# =====================================================
# Chat display
# =====================================================
if len(st.session_state.chat_history) == 1:
    st.info(f"**Bereit für das Gespräch.** Eröffnen Sie den Dialog, indem Sie unten eine Nachricht eingeben oder das Mikrofon nutzen.")
    # st.info(f"**Bereit für das Gespräch.** Eröffnen Sie den Dialog, indem Sie unten eine Nachricht eingeben.")

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

    alignment = "flex-end" if msg["role"] == "user" else "flex-start"

    st.markdown(
        f"""
        <div style="display:flex; justify-content:{alignment};">
            <div class="chat-bubble"
                style="background-color:{bg_color}; color:{text_color}; max-width:65%;">
                <b>{label}:</b><br>{msg['content']}
            </div>
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

    st.markdown("<hr style='margin-top:0; border-color:#2D3748;'>", unsafe_allow_html=True)
    
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
            if st.button("Neues Gespräch beginnen", use_container_width=True, type="primary"):
                for key in [
                    "chat_history",
                    "finished",
                    "mentor_feedback",
                    "current_scenario",
                ]:
                    st.session_state.pop(key, None)
                st.rerun()
