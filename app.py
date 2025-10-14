import streamlit as st
import os, uuid
from openai import OpenAI
from datetime import date, datetime

try:
    from kerykeion import AstrologicalSubject
    KERYKEION_AVAILABLE = True
except ImportError:
    KERYKEION_AVAILABLE = False

# ---------- Setup ----------
st.set_page_config(page_title="🔮 AstroGen", page_icon="✨", layout="centered")

api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("🚨 Missing API key in .streamlit/secrets.toml or environment.")
    st.stop()

client = OpenAI(api_key=api_key)

st.title("🔮 AstroGen — Your AI Astrology Companion")
st.caption("Get personalized KP-style insights for Overall Life, Career, and Relationships.")

# Hidden session id
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]

# Initialize birth_details in session state
if "birth_details" not in st.session_state:
    st.session_state.birth_details = None

# ---------- Birth details form ----------
with st.form("birth_form"):
    st.subheader("Enter your birth details")
    col1, col2 = st.columns(2)
    with col1:
        dob = st.date_input(
            "Date of Birth",
            value=date(1990, 1, 1),
            min_value=date(1900, 1, 1),
            max_value=date.today(),
            help="You can also type the date manually as YYYY-MM-DD.",
        )
        place = st.text_input("Place of Birth (City, Country)")
    with col2:
        tob = st.time_input("Time of Birth (24-hour format)")
        gender = st.selectbox("Gender", ["Male", "Female", "Other"])
    submitted = st.form_submit_button("Generate My Astrology Summary ✨")

# Save birth details to session state when form is submitted
if submitted:
    st.session_state.birth_details = {
        "dob": dob,
        "tob": tob,
        "place": place,
        "gender": gender
    }

# Check if birth details exist in session state
if st.session_state.birth_details is None:
    st.info("Please enter your birth details and click the button above.")
    st.stop()

# Get birth details from session state
birth_data = st.session_state.birth_details
birth_summary = f"""
**Date:** {birth_data['dob']}  
**Time:** {birth_data['tob']}  
**Place:** {birth_data['place']}  
**Gender:** {birth_data['gender']}
"""

st.success("✅ Birth details captured successfully.")
st.markdown("### 🪄 Your Birth Summary")
st.markdown(birth_summary)

# ---------- Calculate Lagna, Moon Sign, Sun Sign using Kerykeion ----------
if "chart_basics" not in st.session_state or submitted:
    with st.spinner("Calculating your astrological chart..."):
        if not KERYKEION_AVAILABLE:
            st.session_state["chart_basics"] = """
⚠️ **Kerykeion library not installed.**

To get accurate astrological calculations, please run:
```bash
pip install kerykeion
```

Then restart your Streamlit app.
"""
        else:
            try:
                # Extract date and time components
                year = birth_data['dob'].year
                month = birth_data['dob'].month
                day = birth_data['dob'].day
                hour = birth_data['tob'].hour
                minute = birth_data['tob'].minute
                
                # Parse city and nation from place
                place_parts = birth_data['place'].split(',')
                city = place_parts[0].strip() if len(place_parts) > 0 else "Mumbai"
                nation = place_parts[-1].strip() if len(place_parts) > 1 else "IN"
                
                # Create astrological chart
                chart = AstrologicalSubject(
                    name="User",
                    year=year,
                    month=month,
                    day=day,
                    hour=hour,
                    minute=minute,
                    city=city,
                    nation=nation
                )
                
                # Get the signs (full names)
                sign_names = {
                    'Ari': 'Aries', 'Tau': 'Taurus', 'Gem': 'Gemini',
                    'Can': 'Cancer', 'Leo': 'Leo', 'Vir': 'Virgo',
                    'Lib': 'Libra', 'Sco': 'Scorpio', 'Sag': 'Sagittarius',
                    'Cap': 'Capricorn', 'Aqu': 'Aquarius', 'Pis': 'Pisces'
                }
                
                lagna = sign_names.get(chart.first_house['sign'], chart.first_house['sign'])
                moon_sign = sign_names.get(chart.moon['sign'], chart.moon['sign'])
                sun_sign = sign_names.get(chart.sun['sign'], chart.sun['sign'])
                
                # Format the output
                chart_info = f"""
**🔺 Lagna (Ascendant):** {lagna}  
**🌙 Moon Sign (Rashi):** {moon_sign}  
**☀️ Sun Sign:** {sun_sign}

📍 Location: {chart.city}, {chart.nation}  
🌍 Coordinates: {chart.lat:.2f}°N, {chart.lng:.2f}°E
"""
                st.session_state["chart_basics"] = chart_info
                st.session_state["chart_object"] = chart  # Store for future use
                
            except Exception as e:
                st.session_state["chart_basics"] = f"""
⚠️ **Error calculating chart:** {str(e)}

**Common issues:**
- City name not recognized (try major city nearby)
- Invalid date/time format
- Network issue (kerykeion needs internet for coordinates)

**Tip:** Use format like "Mumbai, India" or "New York, US"
"""

# Display chart basics
st.markdown("### 🌙 Your Astrological Foundation")
with st.container(border=True):
    st.markdown(st.session_state["chart_basics"])
    st.caption("💡 These form the basis of your astrological reading")

st.info("👇 Click below to get detailed predictions for specific life areas")

# ---------- Optimized Agent Prompts (Token-Efficient) ----------
AGENTS = {
    "overall": """Expert KP & Vedic astrologer. Analyze birth details using:
- KP cuspal/sub-lord method
- Vedic dashas, yogas, transits
Give: 3-line summary, key predictions (High/Medium/Low confidence), safe remedies (mantra/charity/behavioral), timing windows. Be direct, compassionate, non-deterministic. Include disclaimer: not medical/legal advice.""",
    
    "career": """Career-focused KP & Vedic astrologer. Analyze:
- 10th house (KP sub-lord, Vedic strength)
- Dashas, transits affecting career
- Yogas for profession
Give: Career trajectory, promotion/change timing, confidence levels, actionable remedies (low-cost first). Motivational, precise, practical.""",
    
    "relationship": """Relationship-expert KP & Vedic astrologer. Analyze:
- 7th house (KP sub-lord, Venus/Mars placement)
- Navamsa chart, relationship yogas
- Timing via dashas/transits
Give: Partnership insights, marriage timing (if asked), compatibility notes, confidence levels, gentle remedies. Empathetic, kind, realistic."""
}

# ---------- UI ----------
st.markdown("---")
st.markdown("## 🔮 Your Personalized Readings")

def get_reading(agent, prompt):
    """Fetch reading from OpenAI and store in session state"""
    try:
        with st.spinner("Consulting the stars..."):
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Better quality, similar cost to 3.5-turbo
                messages=[
                    {"role": "system", "content": AGENTS[agent]},
                    {"role": "user", "content": f"Birth: {birth_data['dob']}, {birth_data['tob']}, {birth_data['place']}, {birth_data['gender']}. {prompt}"},
                ],
                max_tokens=650,
                temperature=0.7,
            )
        st.session_state[f"{agent}_result"] = response.choices[0].message.content.strip()
    except Exception as e:
        st.session_state[f"{agent}_result"] = f"⚠️ Error: {e}"

# Full-width vertical layout for each reading
st.markdown("### 🌟 Overall Life")
st.button("Get Overall Reading",
          on_click=get_reading,
          args=("overall", "Give overall life prediction with timing and remedies."),
          key="btn_overall",
          use_container_width=True)
if "overall_result" in st.session_state:
    with st.container(border=True):
        st.markdown(st.session_state["overall_result"])

st.markdown("---")

st.markdown("### 💼 Career")
st.button("Get Career Reading",
          on_click=get_reading,
          args=("career", "Analyze career prospects, growth timing, and remedies."),
          key="btn_career",
          use_container_width=True)
if "career_result" in st.session_state:
    with st.container(border=True):
        st.markdown(st.session_state["career_result"])

st.markdown("---")

st.markdown("### 💖 Relationship")
st.button("Get Relationship Reading",
          on_click=get_reading,
          args=("relationship", "Analyze relationship potential, marriage timing, and remedies."),
          key="btn_relationship",
          use_container_width=True)
if "relationship_result" in st.session_state:
    with st.container(border=True):
        st.markdown(st.session_state["relationship_result"])

st.markdown("---")
st.caption("Made with ❤️ using Streamlit + OpenAI | KP-style personalized astrology 🔮")