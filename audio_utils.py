import streamlit.components.v1 as components
import json
import re

def format_for_tts(text: str) -> str:
    # Listen / Aufzählungen
    text = re.sub(r"\n\s*[-•]\s*", ". ", text)

    # Absatzumbrüche → deutliche Pause
    text = re.sub(r"\n{2,}", ". ", text)

    # Einzelne Zeilenumbrüche → kurze Pause
    text = text.replace("\n", " ")

    # Whitespace normalisieren
    text = re.sub(r"\s+", " ", text)

    return text.strip()

def tts_browser(text):
    """Uses Web Speech API to read text. Cleans strings for JS compatibility."""
    if not text:
        return
    
    tts_text = format_for_tts(text)

    clean_text = json.dumps(tts_text)

    js_code = f"""
    <script>
    (function() {{
        window.speechSynthesis.cancel(); 
        var msg = new SpeechSynthesisUtterance({clean_text});
        msg.lang = 'de-DE';
        window.speechSynthesis.speak(msg);
    }})();
    </script>
    """
    components.html(js_code, height=0)

def stop_browser_speech():
    """Immediately halts the browser's speech synthesis engine."""
    js_code = """
    <script>
    window.speechSynthesis.cancel();
    </script>
    """
    components.html(js_code, height=0)

def stt_browser():
    """
    Triggers the browser's SpeechRecognition API.
    Captures audio, sends it to the hidden Streamlit widget, and auto-submits the form.
    """
    js_code = """
    <script>
    var recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = 'de-DE';
    recognition.interimResults = false;
    recognition.start();

    recognition.onresult = function(event) {{
        var transcript = event.results[0][0].transcript;

        window.parent.postMessage({{
            type: 'streamlit:set_widget_value',
            data: {{ value: transcript, widgetId: 'chat_input' }}
        }}, '*');

        setTimeout(function() {{
            const textArea = window.parent.document.querySelector('textarea[data-testid="stChatInputTextArea"]');
            if (textArea) {{
                textArea.value = transcript;
                textArea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                
                const enterEvent = new KeyboardEvent('keydown', {{
                    bubbles: true, cancelable: true, key: 'Enter', code: 'Enter', keyCode: 13
                }});
                textArea.dispatchEvent(enterEvent);
            }}
        }}, 300);
    }};
    </script>
    """
    components.html(js_code, height=0)
