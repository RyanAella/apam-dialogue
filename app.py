import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
import os
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="SI Dialogue Lab")
st.title("SI Dialogue Lab")

# Session State initialisieren
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "system", "content": "Du bist ein hilfreicher Mentor. Antworte kurz."}]

# --- DER MOTOR: PROZESS-FUNKTION ---
def send_to_ai(prompt):
    if prompt:
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.spinner("KI antwortet..."):
            res = client.chat.completions.create(
                model="gpt-4o",
                messages=st.session_state.chat_history
            )
            answer = res.choices[0].message.content
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
        st.rerun()

# --- VERSTECKTER RECEIVER ---
# Wir nutzen ein normales Textfeld, das wir später per JS füllen
input_placeholder = st.empty()
voice_val = input_placeholder.text_input("Receiver", key="receiver", label_visibility="collapsed")

# Falls Text im Receiver landet -> Sofort verarbeiten
if voice_val:
    # Reset des Feldes durch Überschreiben des Placeholders
    input_placeholder.empty() 
    send_to_ai(voice_val)

# --- CHAT ANZEIGE ---
for msg in st.session_state.chat_history:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# --- DER JAVASCRIPT-BUTTON ---
st.markdown("---")
st.subheader("🎤 Spracheingabe")

components.html("""
    <div style="display:flex; flex-direction:column; align-items:center; gap:10px;">
        <button id="startBtn" style="width:100%; padding:15px; border-radius:10px; border:none; background-color:#FF4B4B; color:white; font-weight:bold; cursor:pointer;">
            KLICKEN & SPRECHEN
        </button>
        <p id="status" style="font-family:sans-serif; color:gray;">Bereit...</p>
    </div>

    <script>
    const btn = document.getElementById('startBtn');
    const status = document.getElementById('status');

    btn.onclick = () => {
        const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!Recognition) { status.innerText = "Browser nicht unterstützt"; return; }
        
        const rec = new Recognition();
        rec.lang = 'de-DE';

        rec.onstart = () => {
            status.innerText = "🔴 Ich höre zu... (Sprechen Sie jetzt)";
            btn.style.backgroundColor = "#ff7272";
        };

        rec.onresult = (e) => {
            const text = e.results[0][0].transcript;
            status.innerText = "✅ Erkannt: " + text;
            
            // DER ENTSCHEIDENDE TEIL:
            // Wir suchen das Input-Feld im Hauptfenster und simulieren eine manuelle Eingabe
            const inputs = window.parent.document.querySelectorAll('input[type="text"]');
            const receiver = inputs[0]; // Das erste Textfeld (unser Receiver)
            
            if (receiver) {
                // Wert setzen
                const lastValue = receiver.value;
                receiver.value = text;
                
                // Streamlit "Enter" Event simulieren
                const event = new Event('input', { bubbles: true });
                receiver.dispatchEvent(event);
                
                const enterEvent = new KeyboardEvent('keydown', {
                    key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true
                });
                receiver.dispatchEvent(enterEvent);
            }
        };

        rec.onend = () => {
            btn.style.backgroundColor = "#FF4B4B";
        };

        rec.start();
    };
    </script>
""", height=150)

# --- 10. END SESSION ---
st.divider()
if not st.session_state.finished:
    if st.button("Beenden & Feedback", type="primary"):
        st.session_state.finished = True
        st.rerun()
else:
    st.header("Mentor Feedback")
    if "mentor_feedback" not in st.session_state:
        with st.spinner("Analysiere..."):
            chat_list = [m for m in st.session_state.chat_history if m["role"] != "system"]
            resp = client.chat.completions.create(model=model, messages=[
                {"role": "system", "content": mentor_instructions},
                {"role": "user", "content": str(chat_list)}
            ])
            st.session_state.mentor_feedback = resp.choices[0].message.content
    st.markdown(st.session_state.mentor_feedback)