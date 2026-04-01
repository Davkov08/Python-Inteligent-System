import streamlit as st
from openai import OpenAI

# --- Подесување на страницата ---
st.set_page_config(page_title="AI Smart Class Assistant", page_icon="🎓")

# Инициализација на OpenAI клиент со API клуч од Streamlit secrets
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- Заглавие и стил ---
st.title("🎓 AI Smart Class Assistant")
st.markdown("---")

# --- Сесија за зачувување на податоци ---
if 'transcript' not in st.session_state:
    st.session_state['transcript'] = ""
if 'summary' not in st.session_state:
    st.session_state['summary'] = ""

# --- 1. Прикачување и транскрипција ---
st.header("1. Сними или прикачи предавање")
uploaded_file = st.file_uploader("Прикачи аудио (MP3, WAV, M4A)", type=["mp3", "wav", "m4a"])

if uploaded_file and st.button("🚀 Процесирај го предавањето"):
    with st.spinner('Транскрибирање со Whisper AI...'):
        try:
            # Whisper API може да прима директно file-like object
            transcript_response = client.audio.transcriptions.create(
                model="whisper-1",
                file=uploaded_file
            )
            st.session_state['transcript'] = transcript_response.text
            st.success("Успешна транскрипција!")
        except Exception as e:
            st.error(f"Се случи грешка при транскрипцијата: {e}")

# --- 2. Приказ на резултатите ---
if st.session_state['transcript']:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📝 Цел Текст")
        st.write(st.session_state['transcript'])

    with col2:
        if st.button("✨ Генерирај Резиме и Литература"):
            with st.spinner('Анализирање на лекцијата...'):
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {
                                "role": "system",
                                "content": "Ти си академски асистент. Направи кратко резиме на македонски и препорачај 3 извори на литература (книги/курсеви)."
                            },
                            {"role": "user", "content": st.session_state['transcript']}
                        ]
                    )
                    st.session_state['summary'] = response.choices[0].message.content
                except Exception as e:
                    st.error(f"Грешка при генерација на резиме: {e}")

        if st.session_state['summary']:
            st.subheader("📚 Резиме и Препораки")
            st.info(st.session_state['summary'])

    # --- 3. Интелигентен чет-бот ---
    st.markdown("---")
    st.header("🤖 Прашај го асистентот")
    user_query = st.text_input("Што не ти е јасно од оваа лекција?")

    if user_query:
        with st.spinner('Размислувам...'):
            try:
                chat_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": f"Одговарај само врз основа на овој текст: {st.session_state['transcript']}. Објасни едноставно и биди прецизен."
                        },
                        {"role": "user", "content": user_query}
                    ]
                )
                st.chat_message("assistant").write(chat_response.choices[0].message.content)
            except Exception as e:
                st.error(f"Грешка при одговор на прашањето: {e}")

    # --- 4. Квиз за вежбање ---
    if st.button("📝 Генерирај Квиз за вежбање"):
        with st.spinner('Создавам прашања...'):
            try:
                quiz_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": f"Направи 3 прашања со повеќекратен избор базирани на овој текст: {st.session_state['transcript']}"
                        }
                    ]
                )
                st.write(quiz_response.choices[0].message.content)
            except Exception as e:
                st.error(f"Грешка при генерирање на квиз: {e}")

else:
    st.info("Ве молам прикачете аудио фајл за да започнете.")
