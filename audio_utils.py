import streamlit.components.v1 as components
import json
import re

def format_for_tts(text: str) -> str:
    """
    Cleans text for browser TTS (Markdown, lists, headings, whitespace).
    """
    if not text:
        return ""

    # Remove Markdown links, keep link text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove Markdown images, keep alt text
    text = re.sub(r'!\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove bold, italic, inline code
    text = re.sub(r'(\*\*|__|\*|_|`)', '', text)
    # Remove heading symbols (#)
    text = re.sub(r'^\s*#+\s*', '', text, flags=re.MULTILINE)
    # Convert list items to sentences
    text = re.sub(r"\n\s*[-•]\s*", ". ", text)
    # Paragraph breaks → longer pause
    text = re.sub(r"\n{2,}", ". ", text)
    # Single line breaks → short pause
    text = text.replace("\n", " ")
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def tts_browser_queued(text: str):
    """
    Adds text to a global browser TTS queue.
    Texts are spoken sequentially without overlap.
    """
    if not text:
        return

    clean_text = json.dumps(format_for_tts(text))

    js_code = f"""
    <script>
    (function() {{
        // Initialize global queue once
        if (!window.__ttsQueue) {{
            window.__ttsQueue = [];
            window.__ttsSpeaking = false;
        }}

        function speakNext() {{
            if (window.__ttsSpeaking || window.__ttsQueue.length === 0) return;
            window.__ttsSpeaking = true;
            const text = window.__ttsQueue.shift();
            const msg = new SpeechSynthesisUtterance(text);
            msg.lang = 'de-DE';
            msg.onend = function() {{
                window.__ttsSpeaking = false;
                speakNext();
            }};
            msg.onerror = function() {{
                window.__ttsSpeaking = false;
                speakNext();
            }};
            window.speechSynthesis.speak(msg);
        }}

        window.__ttsQueue.push({clean_text});
        speakNext();
    }})();
    </script>
    """
    components.html(js_code, height=0)


def tts_browser(text: str):
    """
    Cancels all speech and speaks immediately (hard interrupt).
    """
    if not text:
        return

    clean_text = json.dumps(format_for_tts(text))

    js_code = f"""
    <script>
    (function() {{
        window.speechSynthesis.cancel();
        window.__ttsQueue = [];
        window.__ttsSpeaking = false;

        const msg = new SpeechSynthesisUtterance({clean_text});
        msg.lang = 'de-DE';
        window.speechSynthesis.speak(msg);
    }})();
    </script>
    """
    components.html(js_code, height=0)


def stop_browser_speech():
    """
    Stops all queued and active speech immediately.
    """
    js_code = """
    <script>
        window.speechSynthesis.cancel();
        window.__ttsQueue = [];
        window.__ttsSpeaking = false;
    </script>
    """
    components.html(js_code, height=0)


def stt_browser(widget_id="chat_input"):
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

        // Send transcript to Streamlit widget
        window.parent.postMessage({{
            type: 'streamlit:set_widget_value',
            data: {{ value: transcript, widgetId: '{widget_id}' }}
        }}, '*');

        // Auto-insert into textarea (if exists) and submit
        setTimeout(function() {{
            const textArea = window.parent.document.querySelector('textarea[data-testid="stChatInputTextArea"]');
            if (textArea) {{
                textArea.value = transcript;
                textArea.dispatchEvent(new Event('input', {{ bubbles: true }}))
                
                const enterEvent = new KeyboardEvent('keydown', {{
                    bubbles: true, cancelable: true, key: 'Enter', code: 'Enter', keyCode: 13
                }});
                textArea.dispatchEvent(enterEvent);
            }}
        }}, 300);
    }};
    recognition.onerror = function(event) {{
        console.warn('STT Error:', event.error);
    }};
    </script>
    """
    components.html(js_code, height=0)