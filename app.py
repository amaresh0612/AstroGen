import streamlit as st
import os
import uuid
from openai import OpenAI

# --- API Key Setup ---
api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("🚨 OpenAI API key not found! Please set it in .streamlit/secrets.toml or environment variables.")
    st.stop()

client = OpenAI(api_key=api_key)

# --- Page Setup ---
st.set_page_config(page_title="🔮 AstroInsights", page_icon="✨", layout="centered")
st.title("🔮 AstroInsights – Your AI Astrology Companion")
st.caption("Chat with specialized AI astrologers for Career, Relationship, and Overall Life 🌟")

# --- Session-based user ID ---
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]
st.info(f"🪄 Session ID: `{st.session_state.user_id}` (unique for your chat)")

# --- Get birth details ---
birth_details = st.text_area(
    "Enter your birth details (Date, Time, Place, Gender):",
    placeholder="e.g., 12 June 1990, 4:30 AM, Hyderabad, Male",
    key="birth_details"
)
if not birth_details.strip():
    st.info("Please enter your birth details to start.")
    st.stop()

# --- Define agent system prompts ---
AGENTS = {
    "career": "You are an expert astrologer specializing in career predictions. Give precise, motivational, and actionable guidance.",
    "relationship": "You are an astrologer focusing on relationship and emotional well-being. Offer kind, empathetic, and insightful responses.",
    "overall": "You are a holistic astrologer guiding users about overall life trends, balance, and energy flow.",
}

# --- Initialize chat history for each agent ---
for agent in AGENTS:
    if f"{agent}_history" not in st.session_state:
        st.session_state[f"{agent}_history"] = [
            {"role": "system", "content": AGENTS[agent]},
            {"role": "user", "content": f"My birth details are: {birth_details}. Please share my {agent} prediction."},
        ]

# --- OpenAI call helper ---
def ask_openai(chat_history):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=chat_history,
            max_tokens=500,
            temperature=0.8,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Error: {e}"

# --- Tabs for each astrologer ---
tabs = st.tabs(["🧑‍💼 Career", "💕 Relationship", "🌟 Overall"])

for agent, tab in zip(AGENTS.keys(), tabs):
    with tab:
        st.markdown(f"### Chat with your {agent.capitalize()} astrologer ✨")

        # Show past messages
        for msg in st.session_state[f"{agent}_history"]:
            if msg["role"] == "user":
                st.chat_message("user").markdown(msg["content"])
            elif msg["role"] == "assistant":
                st.chat_message("assistant").markdown(msg["content"])

        # Clear chat button
        if st.button(f"🧹 Clear {agent.capitalize()} Chat", key=f"clear_{agent}"):
            st.session_state[f"{agent}_history"] = [
                {"role": "system", "content": AGENTS[agent]},
                {"role": "user", "content": f"My birth details are: {birth_details}. Please share my {agent} prediction."},
            ]
            st.success(f"{agent.capitalize()} chat reset successfully!")
            st.rerun()

        # Chat input per tab
        if user_input := st.chat_input(f"Ask about your {agent}..."):
            st.session_state[f"{agent}_history"].append({"role": "user", "content": user_input})

            with st.spinner("Consulting the stars... 🌠"):
                reply = ask_openai(st.session_state[f"{agent}_history"])

            st.session_state[f"{agent}_history"].append({"role": "assistant", "content": reply})
            st.rerun()

st.markdown("---")
st.caption("Made with ❤️ using Streamlit + OpenAI | Session-based personalized astrology 🔮")
