import streamlit as st
from openai import OpenAI
import re

# --- Подесување на страницата ---
st.set_page_config(
    page_title="AI Smart Class Assistant",
    page_icon="🎓",
    layout="wide"
)

# --- Верификација на API клуч ---
def get_openai_client():
    """Безбедно иницијализирање на OpenAI клиент со валидација."""
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except KeyError:
        st.error("❌ **Грешка:** `OPENAI_API_KEY` не е пронајден во Streamlit secrets.")
        st.markdown("""
        **Како да го поставите:**
        1. Отворете го вашиот проект на [share.streamlit.io](https://share.streamlit.io)
        2. Одете во **Settings → Secrets**
        3. Додајте:
        ```toml
        OPENAI_API_KEY = "sk-proj-ваш_вистински_клуч_овде"
        ```
        4. Земете нов клуч од [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
        """)
        st.stop()

    # Основна валидација на форматот на клучот
    if not api_key.startswith("sk-") or len(api_key) < 40:
        st.error("❌ **Неправилен формат на API клуч.** Клучот треба да започнува со `sk-` и да биде доволно долг.")
        st.stop()

    return OpenAI(api_key=api_key)


# --- Иницијализација ---
client = get_openai_client()

# --- Сесија за зачувување на податоци ---
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
# 1. ПРИКАЧУВАЊЕ И ТРАНСКРИПЦИЈА
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
        st.error(f"❌ Фајлот е поголем од {MAX_FILE_MB} MB. Те молам користи пократок аудио запис.")
    else:
        if st.button("🚀 Процесирај го предавањето", type="primary"):
            with st.spinner("Транскрибирање со Whisper AI... (може да трае 1-2 мин)"):
                try:
                    # Ресетирај ја претходната сесија ако е нов фајл
                    if uploaded_file.name != st.session_state['file_name']:
                        st.session_state['transcript'] = ""
                        st.session_state['summary'] = ""
                        st.session_state['chat_history'] = []
                        st.session_state['quiz_data'] = []
                        st.session_state['quiz_submitted'] = False
                        st.session_state['file_name'] = uploaded_file.name

                    uploaded_file.seek(0)
                    transcript_response = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=(uploaded_file.name, uploaded_file.read(), uploaded_file.type),
                        response_format="text"
                    )
                    st.session_state['transcript'] = transcript_response
                    st.success("✅ Транскрипцијата е успешна!")
                except Exception as e:
                    error_msg = str(e)
                    if "401" in error_msg or "invalid_api_key" in error_msg:
                        st.error("❌ **Неправилен API клуч.** Провери го клучот во Streamlit Secrets и увери се дека е активен на platform.openai.com")
                    elif "429" in error_msg:
                        st.error("⚠️ **Premногу барања.** Вашиот OpenAI акаунт го достигна лимитот. Обидете се подоцна или проверете го billing-от.")
                    elif "insufficient_quota" in error_msg:
                        st.error("💳 **Нема кредити.** Додајте кредити на вашиот OpenAI акаунт на platform.openai.com/settings/billing")
                    else:
                        st.error(f"❌ Грешка при транскрипцијата: {e}")

# ─────────────────────────────────────────────
# 2. РЕЗУЛТАТИ (само ако има транскрипт)
# ─────────────────────────────────────────────
if st.session_state['transcript']:
    st.markdown("---")

    col1, col2 = st.columns([1, 1], gap="large")

    # --- Транскрипт ---
    with col1:
        st.subheader("📝 Транскрипт")
        with st.expander("Прикажи целиот текст", expanded=True):
            st.write(st.session_state['transcript'])
        st.download_button(
            label="⬇️ Преземи транскрипт (.txt)",
            data=st.session_state['transcript'],
            file_name="transkript.txt",
            mime="text/plain"
        )

    # --- Резиме и литература ---
    with col2:
        st.subheader("📚 Резиме и Литература")
        if st.button("✨ Генерирај Резиме и Литература"):
            with st.spinner("Анализирање на лекцијата..."):
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "Ти си академски асистент. Од дадениот транскрипт:\n"
                                    "1. Напиши кратко резиме (3-5 реченици) на македонски јазик\n"
                                    "2. Издвој 5 клучни концепти/термини\n"
                                    "3. Препорачај 3 конкретни извори (книги или онлајн курсеви) со кратки описи\n"
                                    "Користи markdown форматирање со наслови."
                                )
                            },
                            {"role": "user", "content": st.session_state['transcript']}
                        ],
                        temperature=0.4
                    )
                    st.session_state['summary'] = response.choices[0].message.content
                except Exception as e:
                    st.error(f"❌ Грешка при генерација на резиме: {e}")

        if st.session_state['summary']:
            st.markdown(st.session_state['summary'])
            st.download_button(
                label="⬇️ Преземи резиме (.txt)",
                data=st.session_state['summary'],
                file_name="rezime.txt",
                mime="text/plain"
            )

    # ─────────────────────────────────────────────
    # 3. ЧЕТ-БОТ СО ИСТОРИЈА
    # ─────────────────────────────────────────────
    st.markdown("---")
    st.header("🤖 Прашај го асистентот")
    st.caption("Асистентот одговара само врз основа на транскриптот.")

    # Прикажи историја на разговорот
    for msg in st.session_state['chat_history']:
        st.chat_message(msg["role"]).write(msg["content"])

    user_query = st.chat_input("Што не ти е јасно од оваа лекција?")

    if user_query:
        st.session_state['chat_history'].append({"role": "user", "content": user_query})
        st.chat_message("user").write(user_query)

        with st.spinner("Размислувам..."):
            try:
                # Вклучи целата историја на разговор за контекст
                messages = [
                    {
                        "role": "system",
                        "content": (
                            f"Одговарај само врз основа на овој транскрипт:\n\n{st.session_state['transcript']}\n\n"
                            "Ако прашањето не е поврзано со транскриптот, кажи тоа учтиво. "
                            "Одговарај на македонски јазик, јасно и прецизно."
                        )
                    }
                ] + st.session_state['chat_history']

                chat_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    temperature=0.3
                )
                answer = chat_response.choices[0].message.content
                st.session_state['chat_history'].append({"role": "assistant", "content": answer})
                st.chat_message("assistant").write(answer)
            except Exception as e:
                st.error(f"❌ Грешка при одговор: {e}")

    if st.session_state['chat_history']:
        if st.button("🗑️ Исчисти историја на разговор"):
            st.session_state['chat_history'] = []
            st.rerun()

    # ─────────────────────────────────────────────
    # 4. ИНТЕРАКТИВЕН КВИЗ
    # ─────────────────────────────────────────────
    st.markdown("---")
    st.header("📝 Квиз за вежбање")

    if st.button("🎲 Генерирај нов квиз"):
        st.session_state['quiz_submitted'] = False
        st.session_state['quiz_answers'] = {}
        with st.spinner("Создавам прашања..."):
            try:
                quiz_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Генерирај 4 прашања со повеќекратен избор на македонски јазик, "
                                "базирани на дадениот текст. "
                                "Врати го одговорот САМО во следниов JSON формат без никаков дополнителен текст:\n"
                                '{"questions": [{"question": "...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "answer": "A) ..."}]}'
                            )
                        },
                        {"role": "user", "content": st.session_state['transcript']}
                    ],
                    temperature=0.5,
                    response_format={"type": "json_object"}
                )
                import json
                quiz_json = json.loads(quiz_response.choices[0].message.content)
                st.session_state['quiz_data'] = quiz_json.get("questions", [])
            except Exception as e:
                st.error(f"❌ Грешка при генерирање на квиз: {e}")

    # Прикажи го квизот интерактивно
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
                is_correct = user_ans == q['answer']
                if is_correct:
                    correct += 1
                    st.success(f"✅ Прашање {i+1}: Точно!")
                else:
                    st.error(f"❌ Прашање {i+1}: Нeточно. Точен одговор: **{q['answer']}**")

            score_pct = int((correct / len(st.session_state['quiz_data'])) * 100)
            if score_pct == 100:
                st.balloons()
                st.success(f"🏆 Резултат: {correct}/{len(st.session_state['quiz_data'])} ({score_pct}%) — Одлично!")
            elif score_pct >= 50:
                st.warning(f"📊 Резултат: {correct}/{len(st.session_state['quiz_data'])} ({score_pct}%) — Добро, но има простор за подобрување!")
            else:
                st.error(f"📊 Резултат: {correct}/{len(st.session_state['quiz_data'])} ({score_pct}%) — Прочитај го транскриптот повторно.")

else:
    st.info("ℹ️ Прикачете аудио фајл за да започнете.")

# --- Футер ---
st.markdown("---")
st.caption("AI Smart Class Assistant • Powered by OpenAI Whisper & GPT-4o")
