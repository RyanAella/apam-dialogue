### Anleitung: Szenarien anpassen und erstellen

Um die Gesprächs-Szenarien zu verwalten, ist es wichtig zu verstehen, dass jedes Szenario aus **vier zusammengehörigen Dateien** besteht. Hier ist eine Übersicht, welche Dateien zusammengehören und worauf bei Änderungen zu achten ist.

#### 1. Die vier Kern-Dateien eines Szenarios

Jedes Szenario, z.B. mit dem internen Namen `<szenario_name>`, besteht aus den folgenden vier Dateien:

1.  **Die Haupt-Szenario-Datei:**
    *   `scenarios/<szenario_name>_scenario.txt`

2.  **Die drei Prompt-Dateien (KI-Verhalten):**
    *   `prompts/system/<szenario_name>_system_prompt.txt`
    *   `prompts/partner/<szenario_name>_partner_prompt.txt`
    *   `prompts/mentor/<szenario_name>_mentor_prompt.txt`

**Wichtig:** Der `<szenario_name>` (z.B. `yvonne` oder `difficulties`) muss für alle vier Dateien exakt gleich sein, damit die App sie korrekt zuordnen kann.

#### 2. Der Zweck der einzelnen Dateien

*   `scenarios/<szenario_name>_scenario.txt`
    *   **Das ist die Steuerungszentrale.** Sie verbindet alles miteinander und enthält die Anweisungen für den Benutzer.
    *   Sie ist in zwei Bereiche aufgeteilt: `### META ###` und `### GUI INSTRUCTION ###`.
        *   **META-Block:** Legt fest, welcher Titel in der App angezeigt wird (`title:`) und welche Prompt-Dateien geladen werden sollen (`partner_prompt:`, `mentor_prompt:` etc.). Die hier eingetragenen Namen müssen exakt mit den Dateinamen im `prompts`-Ordner übereinstimmen (ohne `.txt`).
        *   **GUI INSTRUCTION-Block:** Der gesamte Text unterhalb dieses Markers ist die Aufgabenbeschreibung, die der Benutzer in der App sieht.

*   `prompts/partner/<szenario_name>_partner_prompt.txt`
    *   **Definiert die KI im Gespräch.** Diese Datei ist entscheidend für das Verhalten des Gesprächspartners. Hier wird die Rolle, die Persönlichkeit, das Ziel und die Hintergrundgeschichte der KI festgelegt.
    *   **Änderungen hier beeinflussen direkt, wie die KI im Dialog antwortet.**

*   `prompts/mentor/<szenario_name>_mentor_prompt.txt`
    *   **Definiert das Feedback.** Diese Datei gibt dem KI-Mentor die Anweisungen, worauf er bei der Analyse des Gesprächs achten und welches Feedback er geben soll.

*   `prompts/system/<szenario_name>_system_prompt.txt`
    *   **Technische Basis.** Enthält übergeordnete Anweisungen für das KI-Modell. Muss in der Regel nicht oft geändert werden.

#### 3. Worauf beim Anpassen zu achten ist

*   **Konsistente Benennung:** Achten Sie darauf, dass der Basis-Dateiname (`<szenario_name>`) über alle vier Dateien hinweg identisch ist.
*   **Korrekte Verlinkung in META:** Die Namen im `META`-Block der `_scenario.txt`-Datei müssen genau auf die zugehörigen Prompt-Dateien verweisen. Ein Tippfehler hier führt dazu, dass die Prompts nicht geladen werden können.
*   **Struktur beibehalten:** Die Marker `### META ###` und `### GUI INSTRUCTION ###` in der `_scenario.txt`-Datei dürfen nicht verändert werden, da die App nach genau diesen Texten sucht.
*   **Keine App-Neustarts nötig:** Die App erkennt neue Szenarien automatisch, sobald eine korrekt benannte `..._scenario.txt`-Datei im `scenarios`-Ordner liegt.
