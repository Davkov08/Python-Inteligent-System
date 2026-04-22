import streamlit as st
import anthropic
from openai import OpenAI
import json

# --- Подесување на страницата ---
st.set_page_config(
    page_title="AI Smart Class Assistant",
    page_icon="🎓",
    layout="wide"
)

# --- Верификација на API клучеви ---
def get_clients():
    """Иницијализирање на OpenAI (само за Whisper) и Anthropic (за сè друго)."""
    errors = []

    try:
        openai_key = st.secrets["OPENAI_API_KEY"]
        openai_client = OpenAI(api_key=openai_key)
    except KeyError:
        openai_client = None
        errors.append("❌ `OPENAI_API_KEY` не е поставен во Secrets (потребен за транскрипција).")

    try:
        anthropic_key = st.secrets["ANTHROPIC_API_KEY"]
        anthropic_client = anthropic.Anthropic(api_key=anthropic_key)
    except KeyError:
        anthropic_client = None
        errors.append("❌ `ANTHROPIC_API_KEY` не е поставен во Secrets (потребен за резиме/чет/квиз).")

    if errors:
        for e in errors:
            st.error(e)
        st.markdown("""
        **Додај ги клучевите во Streamlit → Settings → Secrets:**
        ```toml
        OPENAI_API_KEY = "sk-proj-..."
        ANTHROPIC_API_KEY = "sk-ant-..."
        ```
        - OpenAI клуч: [platform.openai.com/api-keys](https://platform.openai.com/api-keys) — потребен само за Whisper транскрипција
        - Anthropic клуч: [console.anthropic.com](https://console.anthropic.com) — за резиме, чет и квиз
        """)
        st.stop()

    return openai_client, anthropic_client


openai_client, anthropic_client = get_clients()

# --- Сесија ---
defaults = {
    'transcript': "",
    'summary': "",
    'chat_history': [],
    'quiz_data': [],
    'quiz_answers': {},
    'quiz_submitted': False,
    'file_name': "",
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- Заглавие ---
st.title("🎓 AI Smart Class Assistant")
st.markdown("Прикачи аудио предавање → добиј транскрипт, резиме, литература, чет-бот и квиз.")
st.markdown("---")

# ─────────────────────────────────────────────
# 1. ТРАНСКРИПЦИЈА (OpenAI Whisper)
# ─────────────────────────────────────────────
st.header("1. 🎙️ Прикачи предавање")

MAX_FILE_MB = 25
uploaded_file = st.file_uploader(
    f"Поддржани формати: MP3, WAV, M4A (максимум {MAX_FILE_MB} MB)",
    type=["mp3", "wav", "m4a"]
)

if uploaded_file:
    file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
    st.caption(f"📁 Фајл: `{uploaded_file.name}` — {file_size_mb:.1f} MB")

    if file_size_mb > MAX_FILE_MB:
        st.error(f"❌ Фајлот е поголем од {MAX_FILE_MB} MB.")
    else:
        if st.button("🚀 Процесирај го предавањето", type="primary"):
            if uploaded_file.name != st.session_state['file_name']:
                st.session_state.update({
                    'transcript': "", 'summary': "",
                    'chat_history': [], 'quiz_data': [],
                    'quiz_submitted': False, 'file_name': uploaded_file.name
                })

            with st.spinner("Транскрибирање со Whisper AI..."):
                try:
                    uploaded_file.seek(0)
                    transcript_response = openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=(uploaded_file.name, uploaded_file.read(), uploaded_file.type),
                        response_format="text"
                    )
                    st.session_state['transcript'] = transcript_response
                    st.success("✅ Транскрипцијата е успешна!")
                except Exception as e:
                    err = str(e)
                    if "401" in err or "invalid_api_key" in err:
                        st.error("❌ Неправилен OpenAI API клуч. Провери го во Secrets.")
                    elif "429" in err or "quota" in err:
                        st.error("💳 OpenAI rate limit. Додај кредити на platform.openai.com/settings/billing")
                    else:
                        st.error(f"❌ Грешка: {e}")

# ─────────────────────────────────────────────
# 2. РЕЗИМЕ И ЛИТЕРАТУРА (Claude)
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
            with st.spinner("Claude анализира..."):
                try:
                    response = anthropic_client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=1024,
                        system=(
                            "Ти си академски асистент. Од дадениот транскрипт:\n"
                            "1. Напиши кратко резиме (3-5 реченици) на македонски јазик\n"
                            "2. Издвој 5 клучни концепти/термини\n"
                            "3. Препорачај 3 конкретни извори (книги или онлајн курсеви) со кратки описи\n"
                            "Користи markdown форматирање."
                        ),
                        messages=[{"role": "user", "content": st.session_state['transcript']}]
                    )
                    st.session_state['summary'] = response.content[0].text
                except Exception as e:
                    st.error(f"❌ Грешка: {e}")

        if st.session_state['summary']:
            st.markdown(st.session_state['summary'])
            st.download_button(
                "⬇️ Преземи резиме (.txt)",
                data=st.session_state['summary'],
                file_name="rezime.txt",
                mime="text/plain"
            )

    # ─────────────────────────────────────────────
    # 3. ЧЕТ-БОТ СО ИСТОРИЈА (Claude)
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

        with st.spinner("Claude размислува..."):
            try:
                response = anthropic_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    system=(
                        f"Одговарај само врз основа на овој транскрипт:\n\n{st.session_state['transcript']}\n\n"
                        "Ако прашањето не е поврзано со транскриптот, кажи тоа учтиво. "
                        "Одговарај на македонски јазик, јасно и прецизно."
                    ),
                    messages=st.session_state['chat_history']
                )
                answer = response.content[0].text
                st.session_state['chat_history'].append({"role": "assistant", "content": answer})
                st.chat_message("assistant").write(answer)
            except Exception as e:
                st.error(f"❌ Грешка: {e}")

    if st.session_state['chat_history']:
        if st.button("🗑️ Исчисти историја"):
            st.session_state['chat_history'] = []
            st.rerun()

    # ─────────────────────────────────────────────
    # 4. ИНТЕРАКТИВЕН КВИЗ (Claude)
    # ─────────────────────────────────────────────
    st.markdown("---")
    st.header("📝 Квиз за вежбање")

    if st.button("🎲 Генерирај нов квиз"):
        st.session_state['quiz_submitted'] = False
        st.session_state['quiz_answers'] = {}
        with st.spinner("Claude создава прашања..."):
            try:
                quiz_response = anthropic_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    system=(
                        "Генерирај 4 прашања со повеќекратен избор на македонски јазик "
                        "базирани на дадениот текст. "
                        "Врати САМО валиден JSON без никаков друг текст:\n"
                        '{"questions": [{"question": "...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "answer": "A) ..."}]}'
                    ),
                    messages=[{"role": "user", "content": st.session_state['transcript']}]
                )
                raw = quiz_response.content[0].text.strip()
                raw = raw.replace("```json", "").replace("```", "").strip()
                quiz_json = json.loads(raw)
                st.session_state['quiz_data'] = quiz_json.get("questions", [])
            except json.JSONDecodeError:
                st.error("❌ Грешка при читање на квизот. Обиди се повторно.")
            except Exception as e:
                st.error(f"❌ Грешка: {e}")

    if st.session_state['quiz_data']:
        with st.form("quiz_form"):
            for i, q in enumerate(st.session_state['quiz_data']):
                st.markdown(f"**Прашање {i+1}:** {q['question']}")
                st.session_state['quiz_answers'][i] = st.radio(
                    f"q{i}", options=q['options'],
                    key=f"q_{i}", label_visibility="collapsed"
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
                    st.error(f"❌ Прашање {i+1}: Нeточно. Точен одговор: **{q['answer']}**")

            score_pct = int((correct / len(st.session_state['quiz_data'])) * 100)
            if score_pct == 100:
                st.balloons()
                st.success(f"🏆 {correct}/{len(st.session_state['quiz_data'])} ({score_pct}%) — Одлично!")
            elif score_pct >= 50:
                st.warning(f"📊 {correct}/{len(st.session_state['quiz_data'])} ({score_pct}%) — Добро!")
            else:
                st.error(f"📊 {correct}/{len(st.session_state['quiz_data'])} ({score_pct}%) — Прочитај повторно.")

else:
    st.info("ℹ️ Прикачете аудио фајл за да започнете.")

st.markdown("---")
st.caption("AI Smart Class Assistant • Whisper (транскрипција) + Claude (анализа)")
