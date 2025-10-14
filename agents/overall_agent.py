import streamlit as st
from openai import OpenAI
from datetime import date

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.set_page_config(page_title="🔮 AstroGen", page_icon="✨", layout="centered")

st.title("🔮 AstroGen – Your AI Astrology Companion")

# --- birth details form ---
with st.form("birth_form"):
    dob = st.date_input("Date of Birth", value=date(1990, 1, 1))
    tob = st.time_input("Time of Birth (24-hour format)")
    place = st.text_input("Place of Birth (City, Country)")
    gender = st.selectbox("Gender", ["Male", "Female", "Other"])
    submitted = st.form_submit_button("Generate My Astrology Summary ✨")

if not submitted:
    st.stop()

summary = f"Date: {dob}, Time: {tob}, Place: {place}, Gender: {gender}"

st.markdown("### 🪄 Your Birth Summary")
st.markdown(summary)
st.markdown("---")

def overall_agent(chat_history):
    """call OpenAI once"""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # or gpt-4o-mini
        messages=chat_history,
        max_tokens=600,
        temperature=0.8,
    )
    return response.choices[0].message.content.strip()

# ---------- one-shot buttons ----------
cols = st.columns(3)

with cols[0]:
    st.markdown("### 🌟 Overall Life")
    if st.button("Get Overall Reading"):
        chat = [
            {"role": "system", "content": "You are a holistic KP astrologer."},
            {"role": "user", "content": f"My birth details are {summary}. Give my overall life prediction."},
        ]
        with st.spinner("Consulting the stars..."):
            st.session_state["overall"] = overall_agent(chat)

with cols[1]:
    st.markdown("### 💼 Career")
    if st.button("Get Career Reading"):
        chat = [
            {"role": "system", "content": "You are an astrologer specializing in career analysis."},
            {"role": "user", "content": f"My birth details are {summary}. Give my career prediction."},
        ]
        with st.spinner("Analyzing career..."):
            st.session_state["career"] = overall_agent(chat)

with cols[2]:
    st.markdown("### 💖 Relationship")
    if st.button("Get Relationship Reading"):
        chat = [
            {"role": "system", "content": "You are an astrologer focusing on relationships."},
            {"role": "user", "content": f"My birth details are {summary}. Give my relationship prediction."},
        ]
        with st.spinner("Exploring relationships..."):
            st.session_state["relationship"] = overall_agent(chat)

# ---------- show results ----------
for key, title in [("overall", "🌟 Overall Life"), ("career", "💼 Career"), ("relationship", "💖 Relationship")]:
    if key in st.session_state:
        st.markdown("---")
        st.markdown(f"### {title}")
        st.markdown(st.session_state[key])
