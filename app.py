import streamlit as st
import os
import uuid
from openai import OpenAI

# ---------- Setup ----------
api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("🚨 Missing API key in .streamlit/secrets.toml or environment.")
    st.stop()

client = OpenAI(api_key=api_key)

st.set_page_config(page_title="🔮 AstroInsights", page_icon="✨", layout="centered")

# ---------- Title ----------
st.title("🔮 AstroGen – Your AI Astrology Companion")
st.caption("Get personalized KP-style astrology insights for Overall Life, Career, and Relationships.")

# ---------- Session ID (hidden, internal use only) ----------
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]

# ---------- Collect birth details ----------
with st.form("birth_form"):
    st.subheader("Enter your birth details")
    dob = st.date_input("Date of Birth")
    tob = st.time_input("Time of Birth (24-hour format)")
    place = st.text_input("Place of Birth (City, Country)")
    gender = st.selectbox("Gender", ["Male", "Female", "Other"])
    submitted = st.form_submit_button("Generate My Astrology Summary ✨")

if not submitted:
    st.info("Please enter your birth details and click the button above.")
    st.stop()

# ---------- Short summary ----------
birth_summary = f"""
**Date:** {dob}  
**Time:** {tob}  
**Place:** {place}  
**Gender:** {gender}
"""
st.success("✅ Birth details captured successfully.")
st.markdown("### 🪄 Your Birth Summary")
st.markdown(birth_summary)

# ---------- Agent definitions ----------
AGENTS = {
    "overall": "You are a holistic astrologer guiding users about overall life trends, balance, and energy flow. Use KP-style reasoning.",
    "career": "You are an expert astrologer specializing in career predictions. Give precise, motivational, and actionable guidance.",
    "relationship": "You are an astrologer focusing on relationships and emotional well-being. Offer kind, empathetic, and insightful responses."
}

def ask_openai(role_prompt, question):
    """Call the OpenAI API for a one-shot reading."""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",     # use 4o-mini if your account supports it
            messages=[
                {"role": "system", "content": role_prompt},
                {"role": "user", "content": question},
            ],
            max_tokens=600,
            temperature=0.8,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Error: {e}"

# ---------- Layout: three sections ----------
st.markdown("---")
st.markdown("## 🔮 Your Personalized Readings")

col_overall, col_career, col_rel = st.columns(3)

# --- Overall ---
with col_overall:
    st.markdown("### 🌟 Overall Life")
    if st.button("Get Overall Reading"):
        with st.spinner("Consulting the stars..."):
            result = ask_openai(
                AGENTS["overall"],
                f"My birth details are: {birth_summary}. Please give my overall life prediction."
            )
        st.markdown(result)

# --- Career ---
with col_career:
    st.markdown("### 💼 Career")
    if st.button("Get Career Reading"):
        with st.spinner("Analyzing career..."):
            result = ask_openai(
                AGENTS["career"],
                f"My birth details are: {birth_summary}. Please give my career prediction."
            )
        st.markdown(result)

# --- Relationship ---
with col_rel:
    st.markdown("### 💖 Relationship")
    if st.button("Get Relationship Reading"):
        with st.spinner("Exploring relationships..."):
            result = ask_openai(
                AGENTS["relationship"],
                f"My birth details are: {birth_summary}. Please give my relationship prediction."
            )
        st.markdown(result)

st.markdown("---")
st.caption("Made with ❤️ using Streamlit + OpenAI | KP-style personalized astrology 🔮")
