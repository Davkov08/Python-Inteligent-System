import streamlit as st
from openai import OpenAI

# Подесување на страницата
st.set_page_config(page_title="AI Smart Class Assistant", page_icon="🎓")

# Внеси го твојот API Клуч тука
client = OpenAI(api_key=st.secrets["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"])

# --- СТИЛИЗИРАЊЕ И НАСЛОВ ---
st.title("🎓 AI Smart Class Assistant")
st.markdown("---")

# Сесија за зачувување на податоците (за да не се губат при рефреш)
if 'transcript' not in st.session_state:
    st.session_state['transcript'] = ""
if 'summary' not in st.session_state:
    st.session_state['summary'] = ""

# --- 1. ПРИКАЧУВАЊЕ И ТРАНСКРИПЦИЈА ---
st.header("1. Сними или прикачи предавање")
uploaded_file = st.file_uploader("Прикачи аудио (MP3, WAV, M4A)", type=["mp3", "wav", "m4a"])

if uploaded_file and st.button("🚀 Процесирај го предавањето"):
    with st.spinner('Транскрибирање со Whisper AI...'):
        # Привремено зачувување на аудиото
        with open("temp_audio.mp3", "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Whisper API за говор во текст
        audio_file = open("temp_audio.mp3", "rb")
        transcript_response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        st.session_state['transcript'] = transcript_response.text
        st.success("Успешна транскрипција!")

# --- 2. ПРИКАЗ НА РЕЗУЛТАТИТЕ ---
if st.session_state['transcript']:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📝 Цел Текст")
        st.write(st.session_state['transcript'])

    with col2:
        if st.button("✨ Генерирај Резиме и Литература"):
            with st.spinner('Анализирање на лекцијата...'):
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Ти си академски асистент. Направи кратко резиме на македонски и препорачај 3 извори на литература (книги/курсеви)."},
                        {"role": "user", "content": st.session_state['transcript']}
                    ]
                )
                st.session_state['summary'] = response.choices[0].message.content

        if st.session_state['summary']:
            st.subheader("📚 Резиме и Препораки")
            st.info(st.session_state['summary'])

    # --- 3. ИНТЕЛИГЕНТЕН ЧЕТ-БОТ (ПРАШАЊА И ОДГОВОРИ) ---
    st.markdown("---")
    st.header("🤖 Прашај го асистентот")
    user_query = st.text_input("Што не ти е јасно од оваа лекција?")

    if user_query:
        with st.spinner('Размислувам...'):
            chat_response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": f"Одговарај само врз основа на овој текст: {st.session_state['transcript']}. Објасни едноставно и биди прецизен."},
                    {"role": "user", "content": user_query}
                ]
            )
            st.chat_message("assistant").write(chat_response.choices[0].message.content)

    # --- 4. КВИЗ ЗА ПРОВЕРКА (BONUS) ---
    if st.button("📝 Генерирај Квиз за вежбање"):
        with st.spinner('Создавам прашања...'):
            quiz_response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": f"Направи 3 прашања со повеќекратен избор базирани на овој текст: {st.session_state['transcript']}"}]
            )
            st.write(quiz_response.choices[0].message.content)

else:
    st.info("Ве молам прикачете аудио фајл за да започнете.")
