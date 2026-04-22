import streamlit as st
import json
import requests
import tempfile
import os

# ─────────────────────────────────────────────
# КОНФИГУРАЦИЈА
# ─────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL    = "llama3.2"

st.set_page_config(
    page_title="AI Smart Class Assistant",
    page_icon="🎓",
    layout="wide"
)

# ─────────────────────────────────────────────
# ПОМОШНИ ФУНКЦИИ
# ─────────────────────────────────────────────

def check_ollama():
    """Провери дали Ollama серверот е активен."""
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def ollama_chat(system_prompt: str, user_message: str, history: list = None) -> str:
    """Праќа порака до Ollama и враќа одговор."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 1024,
        }
    }
    try:
        r = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=120
        )
        r.raise_for_status()
        data = r.json()
        return data["message"]["content"]
    except requests.exceptions.ConnectionError:
        return "❌ Ollama серверот не е достапен. Стартувај `ollama serve` во терминал."
    except Exception as e:
        return f"❌ Грешка: {e}"


def transcribe_audio(audio_file) -> str:
    """
    Транскрибирај аудио со faster-whisper (локално, без API клуч).
    Користи medium модел за подобра точност.
    За македонски јазик поставено language='mk'.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return (
            "❌ `faster-whisper` не е инсталиран.\n"
            "Изврши: `pip install faster-whisper` па рестартирај ја апликацијата."
        )

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix="." + audio_file.name.split(".")[-1]
    ) as tmp:
        tmp.write(audio_file.read())
        tmp_path = tmp.name

    try:
        # medium = добар баланс помеѓу брзина и точност (~1.5 GB)
        # Смени во "large-v3" за максимална точност (3 GB, побавно)
        # Смени device="cuda" ако имаш NVIDIA GPU (многу побрзо)
        model = WhisperModel("medium", device="cpu", compute_type="int8")

        # language="mk" за македонски — отстрани го ако предавањето е на друг јазик
        segments, info = model.transcribe(tmp_path, beam_size=5, language="mk")

        transcript = " ".join(segment.text for segment in segments)
        return transcript.strip()
    except Exception as e:
        return f"❌ Грешка при транскрипција: {e}"
    finally:
        os.unlink(tmp_path)


# ─────────────────────────────────────────────
# СЕСИЈА
# ─────────────────────────────────────────────
defaults = {
    'transcript':     "",
    'summary':        "",
    'chat_history':   [],
    'quiz_data':      [],
    'quiz_answers':   {},
    'quiz_submitted': False,
    'file_name':      "",
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ─────────────────────────────────────────────
# ЗАГЛАВИЕ
# ─────────────────────────────────────────────
st.title("🎓 AI Smart Class Assistant")
st.markdown("Прикачи аудио предавање → добиј транскрипт, резиме, литература, чет-бот и квиз.")
st.markdown("*(Powered by Ollama + Llama 3.2 — целосно локално, без API трошоци)*")

# --- Статус на Ollama ---
if check_ollama():
    st.success(f"✅ Ollama е активен | Модел: `{OLLAMA_MODEL}`")
else:
    st.error(
        "❌ Ollama не е активен! Отвори PowerShell и изврши: `ollama serve`  |  "
        "Потоа симни модел: `ollama pull llama3.2`"
    )

st.markdown("---")

# ─────────────────────────────────────────────
# 1. ТРАНСКРИПЦИЈА (faster-whisper medium, локално)
# ─────────────────────────────────────────────
st.header("1. 🎙️ Прикачи предавање")

uploaded_file = st.file_uploader(
    "Поддржани формати: MP3, WAV, M4A",
    type=["mp3", "wav", "m4a"]
)

if uploaded_file:
    file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
    st.caption(f"📁 Фајл: `{uploaded_file.name}` — {file_size_mb:.1f} MB")

    st.info(
        "💡 **Модел:** Whisper `medium` (македонски јазик) — "
        "~1.5 GB, прв пат се симнува автоматски. "
        "Брзина: ~1 мин аудио ≈ 1-2 мин процесирање на CPU."
    )

    if st.button("🚀 Процесирај го предавањето", type="primary"):
        if uploaded_file.name != st.session_state['file_name']:
            st.session_state.update({
                'transcript':     "",
                'summary':        "",
                'chat_history':   [],
                'quiz_data':      [],
                'quiz_submitted': False,
                'file_name':      uploaded_file.name
            })

        with st.spinner("Транскрибирање со Whisper medium (македонски)... Ова може да трае неколку минути."):
            uploaded_file.seek(0)
            result = transcribe_audio(uploaded_file)
            if result.startswith("❌"):
                st.error(result)
            else:
                st.session_state['transcript'] = result
                st.success("✅ Транскрипцијата е успешна!")

# ─────────────────────────────────────────────
# 2. РЕЗИМЕ И ЛИТЕРАТУРА (Llama преку Ollama)
# ─────────────────────────────────────────────
if st.session_state['transcript']:
    st.markdown("---")
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("📝 Транскрипт")
        with st.expander("Прикажи целиот текст", expanded=True):
            st.write(st.session_state['transcript'])
        st.download_button(
            "⬇️ Преземи транскрипт (.txt)",
            data=st.session_state['transcript'],
            file_name="transkript.txt",
            mime="text/plain"
        )

    with col2:
        st.subheader("📚 Резиме и Литература")
        if st.button("✨ Генерирај Резиме и Литература"):
            with st.spinner("Llama анализира... (може да трае 30-60 сек)"):
                system_prompt = (
                    "Ти си академски асистент. Од дадениот транскрипт:\n"
                    "1. Напиши кратко резиме (3-5 реченици) на македонски јазик\n"
                    "2. Издвои 5 клучни концепти/термини\n"
                    "3. Препорачај 3 конкретни извори (книги или онлајн курсеви) со кратки описи\n"
                    "Користи markdown форматирање."
                )
                transcript_chunk = st.session_state['transcript'][:4000]
                result = ollama_chat(system_prompt, transcript_chunk)
                st.session_state['summary'] = result

        if st.session_state['summary']:
            st.markdown(st.session_state['summary'])
            st.download_button(
                "⬇️ Преземи резиме (.txt)",
                data=st.session_state['summary'],
                file_name="rezime.txt",
                mime="text/plain"
            )

    # ─────────────────────────────────────────────
    # 3. ЧЕТ-БОТ СО ИСТОРИЈА (Llama преку Ollama)
    # ─────────────────────────────────────────────
    st.markdown("---")
    st.header("🤖 Прашај го асистентот")
    st.caption("Асистентот одговара само врз основа на транскриптот.")

    for msg in st.session_state['chat_history']:
        st.chat_message(msg["role"]).write(msg["content"])

    user_query = st.chat_input("Што не ти е јасно од оваа лекција?")

    if user_query:
        st.session_state['chat_history'].append({"role": "user", "content": user_query})
        st.chat_message("user").write(user_query)

        with st.spinner("Llama размислува..."):
            system_prompt = (
                f"Одговарај само врз основа на овој транскрипт:\n\n"
                f"{st.session_state['transcript'][:3000]}\n\n"
                "Ако прашањето не е поврзано со транскриптот, кажи тоа учтиво. "
                "Одговарај на македонски јазик, јасно и прецизно."
            )
            recent_history = st.session_state['chat_history'][-6:]
            answer = ollama_chat(system_prompt, user_query, history=recent_history[:-1])
            st.session_state['chat_history'].append({"role": "assistant", "content": answer})
            st.chat_message("assistant").write(answer)

    if st.session_state['chat_history']:
        if st.button("🗑️ Исчисти историја"):
            st.session_state['chat_history'] = []
            st.rerun()

    # ─────────────────────────────────────────────
    # 4. ИНТЕРАКТИВЕН КВИЗ (Llama преку Ollama)
    # ─────────────────────────────────────────────
    st.markdown("---")
    st.header("📝 Квиз за вежбање")

    if st.button("🎲 Генерирај нов квиз"):
        st.session_state['quiz_submitted'] = False
        st.session_state['quiz_answers']   = {}

        with st.spinner("Llama создава прашања... (30-60 сек)"):
            system_prompt = (
                "Генерирај 4 прашања со повеќекратен избор на македонски јазик "
                "базирани на дадениот текст. "
                "Врати САМО валиден JSON без никаков друг текст, без markdown, без објаснување:\n"
                '{"questions": [{"question": "...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "answer": "A) ..."}]}'
            )
            raw = ollama_chat(system_prompt, st.session_state['transcript'][:3000])

            raw = raw.strip()
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start != -1 and end > start:
                raw = raw[start:end]

            try:
                quiz_json = json.loads(raw)
                st.session_state['quiz_data'] = quiz_json.get("questions", [])
                if not st.session_state['quiz_data']:
                    st.error("❌ Квизот е празен. Обиди се повторно.")
            except json.JSONDecodeError:
                st.error("❌ Грешка при читање на квизот. Обиди се повторно.")
                st.code(raw, language="text")

    if st.session_state['quiz_data']:
        with st.form("quiz_form"):
            for i, q in enumerate(st.session_state['quiz_data']):
                st.markdown(f"**Прашање {i+1}:** {q['question']}")
                st.session_state['quiz_answers'][i] = st.radio(
                    f"q{i}",
                    options=q['options'],
                    key=f"q_{i}",
                    label_visibility="collapsed"
                )
                st.markdown("")

            submitted = st.form_submit_button("✅ Провери одговори", type="primary")

        if submitted:
            st.session_state['quiz_submitted'] = True

        if st.session_state['quiz_submitted']:
            correct = 0
            for i, q in enumerate(st.session_state['quiz_data']):
                user_ans = st.session_state['quiz_answers'].get(i, "")
                if user_ans == q['answer']:
                    correct += 1
                    st.success(f"✅ Прашање {i+1}: Точно!")
                else:
                    st.error(f"❌ Прашање {i+1}: Неточно. Точен одговор: **{q['answer']}**")

            total     = len(st.session_state['quiz_data'])
            score_pct = int((correct / total) * 100)
            if score_pct == 100:
                st.balloons()
                st.success(f"🏆 {correct}/{total} ({score_pct}%) — Одлично!")
            elif score_pct >= 50:
                st.warning(f"📊 {correct}/{total} ({score_pct}%) — Добро!")
            else:
                st.error(f"📊 {correct}/{total} ({score_pct}%) — Прочитај повторно.")

else:
    st.info("ℹ️ Прикачете аудио фајл за да започнете.")

st.markdown("---")
st.caption("AI Smart Class Assistant • Whisper medium/mk (транскрипција) + Ollama/Llama3.2 (анализа) • 100% локално & бесплатно")
