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

models = client.models.list()

for m in models.data:
    if "gpt" in m.id:
        print(m.id)