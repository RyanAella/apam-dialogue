import os
import re
import streamlit as st

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
SCENARIOS_DIR = os.path.join(os.path.dirname(__file__), "scenarios")


# =====================================================
# Prompt Loader
# =====================================================
def load_prompt(folder: str, name: str) -> str:
    """
    folder: system | partner | mentor
    name: filename without .txt
    """
    path = os.path.join(PROMPTS_DIR, folder, f"{name}.txt")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Prompt nicht gefunden: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
    

# =====================================================
# META + GUI INSTRUCTION Parsing
# =====================================================
def parse_meta_block(text: str) -> tuple[dict, str]:
    """
    Returns:
    - meta dict
    - GUI instruction text (everything AFTER ### GUI INSTRUCTION ###)
    """
    meta = {}
    
    match = re.search(r"### META ###(.*?)### GUI INSTRUCTION ###", text, re.DOTALL)
    
    if match:
        meta_block = match.group(1)
        for line in meta_block.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip()

        gui_text = text.split("### GUI INSTRUCTION ###", 1)[1].strip()
    else:
        gui_text = text.strip()

    return meta, gui_text
    

# =====================================================
# Scenario META Loader
# =====================================================
def load_scenario_meta(scenario_key: str) -> dict:
    path = os.path.join(SCENARIOS_DIR, f"{scenario_key}.txt")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Szenario nicht gefunden: {path}")

    with open(path, "r", encoding="utf-8") as f:
        meta, _ = parse_meta_block(f.read())
    return meta
    

# =====================================================
# Scenario Prompt Loader
# =====================================================
def load_scenario_prompts(scenario_key: str) -> dict:
    meta = load_scenario_meta(scenario_key)

    return {
        "title": meta.get("title", scenario_key),
        "system": load_prompt("system", meta["system_prompt"]),
        "partner": load_prompt("partner", meta["partner_prompt"]),
        "mentor": load_prompt("mentor", meta["mentor_prompt"])
    }


# =====================================================
# Mentor Message Assembly
# =====================================================
def assemble_mentor_messages(mentor_prompt: str, chat_messages: list) -> list:
    transcript = "\n".join(
        f"{m['role']}: {m['content']}" 
        for m in chat_messages 
        if m['role'] != "system"
    )

    return [
        {"role": "system", "content": mentor_prompt},
        {"role": "user", "content": transcript}
    ]


# =====================================================
# Scenario Discovery
# =====================================================
def _discover_scenarios():
    scenarios = {}

    for filename in os.listdir(SCENARIOS_DIR):
        if not filename.endswith("_scenario.txt"):
            continue

        scenario_key = filename.replace(".txt", "")
        path = os.path.join(SCENARIOS_DIR, filename)

        with open(path, "r", encoding="utf-8") as f:
            meta, _ = parse_meta_block(f.read())

        scenarios[scenario_key] = {
            "ui_title": meta.get("title", scenario_key),
            "path": path,
        }

    return scenarios


@st.cache_data
def get_scenarios(folder_mtime: float):
    """Cached scenario discovery (no import-time side effects)."""
    return _discover_scenarios()


# =====================================================
# Role Label Extraction
# =====================================================
def extract_role_label(text: str) -> str:
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
    role = re.split(r"\s+im\s+|\s+in\s+", role_raw, 1)[0]

    # masculine genitive → nominative
    if article == "des" and role.endswith("s"):
        role = role[:-1]

    return role.capitalize()