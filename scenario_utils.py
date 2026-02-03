import os
import re
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")
SCENARIO_DIR = os.path.join(PROMPTS_DIR, "scenarios")
ANALYSIS_DIR = os.path.join(PROMPTS_DIR, "analysis")

# --- Parse META block from scenario file ---
def parse_meta_block(text):
    """
    Extracts meta information from scenario files.  
    Returns dict and the remaining content.
    """
    match = re.search(r"### META ###(.*?)###", text, re.DOTALL)
    if not match:
        return {}, text
    
    meta_block = match.group(1)
    meta = {}

    for line in meta_block.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()

    # Remove meta block from content
    content_without_meta = text.replace(match.group(0), "")

    return meta, content_without_meta


# --- Automatically discover scenarios ---
def discover_scenarios():
    """
    Loads all scenarios and returns a dict:  
    key = meta title (fallback filename)  
    value = dict with paths to scenario and analysis file
    """
    scenarios = {}

    for filename in os.listdir(SCENARIO_DIR):
        if not filename.startswith("scenario_") or not filename.endswith(".txt"):
            continue

        scenario_path = os.path.join(SCENARIO_DIR, filename)

        # --- Read meta from file ---
        try:
            with open(scenario_path, "r", encoding="utf-8") as f:
                raw_content = f.read()
        except FileNotFoundError:
            st.warning(f"Szenario-Datei nicht gefunden: {filename}")
            continue

        meta, _ = parse_meta_block(raw_content)
        ui_title = meta.get("title", filename.replace("scenario_", "").replace(".txt", "").title())

        # Specify analysis file
        base_name = filename.removeprefix("scenario_")
        analysis_file = f"analyze_{base_name}"
        analysis_path = os.path.join(ANALYSIS_DIR, analysis_file)
        if not os.path.isfile(analysis_path):
            st.warning(f"Analyse fehlt für {filename}")
            analysis_path = None

        internal_key = f"{ui_title}::{filename}"
        scenarios[internal_key] = {
            "scenario_path": scenario_path,
            "analysis_path": analysis_path,
            "ui_title": ui_title
        }

    return scenarios


SCENARIOS = discover_scenarios()


# --- Extract role label (robust, multi-word) ---
def extract_role_label(text):
    """
    Extract the role of AI from the scenario text.  
    Example:  
    'DEINE ROLLE IST DIE DES MITARBEITERS IM CONTROLLING-TEAM'
    → 'Mitarbeiter'
    """
    match = re.search(
        r"DEINE\s+ROLLE\s+IST\s+DIE\s+(DES|DER)\s+([A-ZÄÖÜa-zäöüß\s-]+)",
        text,
        re.IGNORECASE
    )

    if not match:
        return "Gesprächspartner*in"

    article = match.group(1).lower()
    role_raw = match.group(2).strip().lower()

    # only take the role stem (cut off everything after the first “in”)
    role_raw = re.split(r"\s+im\s+|\s+in\s+", role_raw, maxsplit=1)[0]

    # masculine genitive → nominative
    if article == "des" and role_raw.endswith("s"):
        role_raw = role_raw[:-1]

    return role_raw.capitalize()


# --- Load Szenario on-demand ---
def load_scenario(internal_key):
    selected_files = SCENARIOS.get(internal_key)
    
    if not selected_files:
        st.error("Szenario nicht gefunden.")
        st.stop()

    scenario_path = selected_files["scenario_path"]
    analysis_path = selected_files["analysis_path"]

    # Load scenario file
    try:
        with open(scenario_path, "r", encoding="utf-8") as f:
            raw_content = f.read()
    except FileNotFoundError:
        st.error(f"Szenario-Datei nicht gefunden: {scenario_path}")
        st.stop()

    # --- Remove META ---
    meta, content_wo_meta = parse_meta_block(raw_content)

    # Determine role name
    ai_display_name = "Gesprächspartner*in"
    if "partner_de =" in content_wo_meta:
        role_part = content_wo_meta.split("partner_de =", 1)[1]
        ai_display_name = extract_role_label(role_part)

    # Split SYSTEM PROMPT
    parts = content_wo_meta.split("### SYSTEM PROMPT ###", 1)
    user_instruction = parts[0].replace("### GUI INSTRUCTION ###", "").strip()
    full_ki_logic = parts[1].strip() if len(parts) > 1 else ""

    # Analysis file
    mentor_instructions = ""
    if analysis_path:
        try:
            with open(analysis_path, "r", encoding="utf-8") as f:
                mentor_instructions = f.read()
        except FileNotFoundError:
            st.warning(f"Analyse-Datei nicht gefunden: {analysis_path}")

    return user_instruction, full_ki_logic, ai_display_name, mentor_instructions