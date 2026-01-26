import os
import re
import streamlit as st

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

def extract_role_label(text):
    """Extracts the character name from the scenario prompt for GUI labeling."""
    match = re.search(r"DU BIST (?:DIE|DER)\s+([A-ZÄÖÜa-zäöü]+)", text)
    if match:
        return match.group(1).strip()
    return "Gesprächspartner*in"

def load_scenario(scenario_name):
    """Loads scenario files and returns the content."""
    selected_files = SCENARIOS[scenario_name]

    scenario_path = os.path.join("prompts", "scenarios", selected_files["scenario"])
    analysis_path = os.path.join("prompts", "analysis", selected_files["analysis"])

    try:
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

    except FileNotFoundError:
        st.error(f"Szenario-Datei nicht gefunden: {scenario_path}")
        st.stop()
        return None, None, None, None

    try:
        with open(analysis_path, "r", encoding="utf-8") as f:
            mentor_instructions = f.read()
    except FileNotFoundError:
        st.error(f"Analyse-Datei nicht gefunden: {analysis_path}")
        st.stop()
        return None, None, None, None

    return user_instruction, full_ki_logic, ai_display_name, mentor_instructions
