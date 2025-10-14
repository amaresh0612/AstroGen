import streamlit as st
import os, uuid
from openai import OpenAI
from datetime import datetime, timedelta
import swisseph as swe
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz

# ---------- Setup ----------
st.set_page_config(page_title="🔮 AstroGen", page_icon="✨", layout="centered")

api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("🚨 Missing API key in .streamlit/secrets.toml or environment.")
    st.stop()

client = OpenAI(api_key=api_key)

st.title("🔮 AstroGen — Your AI Astrology Companion")
st.caption("Get personalized KP-style insights with complete chart analysis")

# Initialize session state
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]

if "birth_details" not in st.session_state:
    st.session_state.birth_details = None

# ---------- Comprehensive KP Calculation Functions ----------

def get_coordinates(place):
    """Get latitude and longitude for a place"""
    try:
        geolocator = Nominatim(user_agent="astrologyapp")
        location = geolocator.geocode(place, timeout=10)
        if location:
            return location.latitude, location.longitude
        return None, None
    except:
        return None, None

def get_timezone_offset(lat, lng, dt):
    """Get timezone offset for given location and datetime"""
    try:
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lat=lat, lng=lng)
        if tz_name:
            tz = pytz.timezone(tz_name)
            offset = tz.utcoffset(dt).total_seconds() / 3600
            return offset
        return 0
    except:
        return 0

def get_sign_name(degree):
    """Convert degree to zodiac sign name"""
    signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
             'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
    sign_num = int(degree / 30)
    degree_in_sign = degree % 30
    return signs[sign_num], degree_in_sign

def get_nakshatra_info(degree):
    """Get Nakshatra (star) and its lord"""
    nakshatras = [
        ('Ashwini', 'Ketu'), ('Bharani', 'Venus'), ('Krittika', 'Sun'),
        ('Rohini', 'Moon'), ('Mrigashira', 'Mars'), ('Ardra', 'Rahu'),
        ('Punarvasu', 'Jupiter'), ('Pushya', 'Saturn'), ('Ashlesha', 'Mercury'),
        ('Magha', 'Ketu'), ('Purva Phalguni', 'Venus'), ('Uttara Phalguni', 'Sun'),
        ('Hasta', 'Moon'), ('Chitra', 'Mars'), ('Swati', 'Rahu'),
        ('Vishakha', 'Jupiter'), ('Anuradha', 'Saturn'), ('Jyeshtha', 'Mercury'),
        ('Mula', 'Ketu'), ('Purva Ashadha', 'Venus'), ('Uttara Ashadha', 'Sun'),
        ('Shravana', 'Moon'), ('Dhanishta', 'Mars'), ('Shatabhisha', 'Rahu'),
        ('Purva Bhadrapada', 'Jupiter'), ('Uttara Bhadrapada', 'Saturn'), ('Revati', 'Mercury')
    ]
    nak_num = int(degree / 13.333333)
    return nakshatras[nak_num % 27]

def get_sublord(degree):
    """Calculate KP Sub-lord"""
    sublords = ['Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury']
    proportions = [7, 20, 6, 10, 7, 18, 16, 19, 17]
    
    nakshatra_portion = (degree % 13.333333) / 13.333333
    cumulative = 0
    total = sum(proportions)
    
    for i, prop in enumerate(proportions):
        cumulative += prop / total
        if nakshatra_portion <= cumulative:
            return sublords[i]
    return sublords[-1]

def calculate_vimshottari_dasha(moon_degree, birth_date):
    """Calculate Vimshottari Dasha periods"""
    # Dasha lords and their periods (in years)
    dasha_lords = ['Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury']
    dasha_years = [7, 20, 6, 10, 7, 18, 16, 19, 17]
    
    # Find starting dasha based on moon's nakshatra
    nak_num = int(moon_degree / 13.333333) % 27
    nak_lord_index = nak_num % 9
    
    # Calculate how much of the nakshatra is completed
    nak_completed = (moon_degree % 13.333333) / 13.333333
    
    # Calculate balance of first dasha
    first_dasha_balance = dasha_years[nak_lord_index] * (1 - nak_completed)
    
    # Create dasha sequence
    dashas = []
    current_date = birth_date
    
    # Add first dasha (balance)
    dashas.append({
        'lord': dasha_lords[nak_lord_index],
        'start': current_date,
        'years': first_dasha_balance,
        'end': current_date + timedelta(days=365.25 * first_dasha_balance)
    })
    current_date = dashas[-1]['end']
    
    # Add remaining dashas (total 120 years cycle)
    for i in range(1, 10):  # Get next 9 dashas
        lord_index = (nak_lord_index + i) % 9
        years = dasha_years[lord_index]
        dashas.append({
            'lord': dasha_lords[lord_index],
            'start': current_date,
            'years': years,
            'end': current_date + timedelta(days=365.25 * years)
        })
        current_date = dashas[-1]['end']
    
    return dashas

def get_current_dasha(dashas, current_date):
    """Find current and upcoming dashas"""
    for i, dasha in enumerate(dashas):
        if dasha['start'] <= current_date <= dasha['end']:
            current = dasha
            upcoming = dashas[i + 1] if i + 1 < len(dashas) else None
            return current, upcoming
    return None, None

def calculate_comprehensive_chart(dob, tob, place):
    """Calculate complete KP chart with all houses, planets, and dashas"""
    try:
        # Get coordinates
        lat, lng = get_coordinates(place)
        if lat is None or lng is None:
            return None, "Could not find location. Try format: 'Mumbai, India'"
        
        # Combine date and time
        dt = datetime.combine(dob, tob)
        
        # Get timezone offset and convert to UTC
        tz_offset = get_timezone_offset(lat, lng, dt)
        utc_dt = dt - timedelta(hours=tz_offset)
        
        # Calculate Julian Day
        jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, 
                        utc_dt.hour + utc_dt.minute/60.0)
        
        # Set KP Ayanamsa
        swe.set_sid_mode(swe.SIDM_KRISHNAMURTI)
        
        # ===== PLANETS =====
        planet_data = {}
        planets = {
            'Sun': swe.SUN,
            'Moon': swe.MOON,
            'Mars': swe.MARS,
            'Mercury': swe.MERCURY,
            'Jupiter': swe.JUPITER,
            'Venus': swe.VENUS,
            'Saturn': swe.SATURN,
            'Rahu': swe.MEAN_NODE,  # North Node
        }
        
        for name, planet_id in planets.items():
            pos = swe.calc_ut(jd, planet_id, swe.FLG_SIDEREAL)[0]
            degree = pos[0] % 360
            sign, deg_in_sign = get_sign_name(degree)
            nak, nak_lord = get_nakshatra_info(degree)
            sublord = get_sublord(degree)
            
            planet_data[name] = {
                'sign': sign,
                'degree': f"{deg_in_sign:.2f}°",
                'nakshatra': nak,
                'nakshatra_lord': nak_lord,
                'sublord': sublord,
                'full_degree': degree
            }
        
        # Ketu is always opposite to Rahu
        rahu_deg = planet_data['Rahu']['full_degree']
        ketu_deg = (rahu_deg + 180) % 360
        sign, deg_in_sign = get_sign_name(ketu_deg)
        nak, nak_lord = get_nakshatra_info(ketu_deg)
        sublord = get_sublord(ketu_deg)
        
        planet_data['Ketu'] = {
            'sign': sign,
            'degree': f"{deg_in_sign:.2f}°",
            'nakshatra': nak,
            'nakshatra_lord': nak_lord,
            'sublord': sublord,
            'full_degree': ketu_deg
        }
        
        # ===== HOUSES (12 CUSPS) =====
        houses_calc = swe.houses(jd, lat, lng, b'P')  # Placidus
        house_cusps = houses_calc[0]
        ascendant = houses_calc[0][0] % 360
        
        house_data = {}
        house_names = ['1st (Lagna)', '2nd', '3rd', '4th', '5th', '6th', 
                       '7th', '8th', '9th', '10th', '11th', '12th']
        
        for i, cusp_deg in enumerate(house_cusps[:12]):
            cusp_deg = cusp_deg % 360
            sign, deg_in_sign = get_sign_name(cusp_deg)
            nak, nak_lord = get_nakshatra_info(cusp_deg)
            sublord = get_sublord(cusp_deg)
            
            house_data[house_names[i]] = {
                'sign': sign,
                'degree': f"{deg_in_sign:.2f}°",
                'nakshatra': nak,
                'nakshatra_lord': nak_lord,
                'sublord': sublord
            }
        
        # ===== DASHA CALCULATION =====
        moon_deg = planet_data['Moon']['full_degree']
        dashas = calculate_vimshottari_dasha(moon_deg, dt)
        current_dasha, upcoming_dasha = get_current_dasha(dashas, datetime.now())
        
        dasha_info = {
            'current': {
                'lord': current_dasha['lord'],
                'start': current_dasha['start'].strftime('%Y-%m-%d'),
                'end': current_dasha['end'].strftime('%Y-%m-%d'),
                'years': f"{current_dasha['years']:.2f}"
            } if current_dasha else None,
            'upcoming': {
                'lord': upcoming_dasha['lord'],
                'start': upcoming_dasha['start'].strftime('%Y-%m-%d'),
                'years': f"{upcoming_dasha['years']:.0f}"
            } if upcoming_dasha else None
        }
        
        # ===== FORMAT FOR DISPLAY =====
        display_text = f"""
### 🏠 House Cusps (Placidus)
**1st House (Lagna):** {house_data['1st (Lagna)']['sign']} | Sub-lord: {house_data['1st (Lagna)']['sublord']}  
**7th House:** {house_data['7th']['sign']} | Sub-lord: {house_data['7th']['sublord']}  
**10th House:** {house_data['10th']['sign']} | Sub-lord: {house_data['10th']['sublord']}

### 🪐 Planetary Positions
**Sun:** {planet_data['Sun']['sign']} | Nak: {planet_data['Sun']['nakshatra']} | Sub: {planet_data['Sun']['sublord']}  
**Moon:** {planet_data['Moon']['sign']} | Nak: {planet_data['Moon']['nakshatra']} | Sub: {planet_data['Moon']['sublord']}  
**Mars:** {planet_data['Mars']['sign']} | Sub: {planet_data['Mars']['sublord']}  
**Mercury:** {planet_data['Mercury']['sign']} | Sub: {planet_data['Mercury']['sublord']}  
**Jupiter:** {planet_data['Jupiter']['sign']} | Sub: {planet_data['Jupiter']['sublord']}  
**Venus:** {planet_data['Venus']['sign']} | Sub: {planet_data['Venus']['sublord']}  
**Saturn:** {planet_data['Saturn']['sign']} | Sub: {planet_data['Saturn']['sublord']}  
**Rahu:** {planet_data['Rahu']['sign']} | Sub: {planet_data['Rahu']['sublord']}  
**Ketu:** {planet_data['Ketu']['sign']} | Sub: {planet_data['Ketu']['sublord']}

### ⏰ Vimshottari Dasha
**Current:** {dasha_info['current']['lord']} Dasha ({dasha_info['current']['start']} to {dasha_info['current']['end']})  
**Upcoming:** {dasha_info['upcoming']['lord']} Dasha (starts {dasha_info['upcoming']['start']})

📍 {place} ({lat:.2f}°, {lng:.2f}°)
"""
        
        return {
            'houses': house_data,
            'planets': planet_data,
            'dashas': dasha_info,
            'location': {'place': place, 'lat': lat, 'lng': lng},
            'display': display_text
        }, None
        
    except Exception as e:
        return None, f"Error: {str(e)}"

# ---------- Birth Details Form ----------
with st.form("birth_form"):
    st.subheader("Enter your birth details")
    col1, col2 = st.columns(2)
    with col1:
        dob = st.date_input(
            "Date of Birth",
            value=datetime(1990, 1, 1).date(),
            min_value=datetime(1900, 1, 1).date(),
            max_value=datetime.today().date(),
        )
        place = st.text_input("Place of Birth", value="Mumbai, India")
    with col2:
        tob = st.time_input("Time of Birth", value=datetime.strptime("12:00", "%H:%M").time())
        gender = st.selectbox("Gender", ["Male", "Female", "Other"])
    
    submitted = st.form_submit_button("Generate Complete KP Chart ✨", use_container_width=True)

if submitted:
    st.session_state.birth_details = {
        "dob": dob,
        "tob": tob,
        "place": place,
        "gender": gender
    }
    if "chart_result" in st.session_state:
        del st.session_state["chart_result"]

if st.session_state.birth_details is None:
    st.info("👆 Please enter your birth details above to begin")
    st.stop()

birth_data = st.session_state.birth_details

st.success("✅ Birth details captured")
with st.expander("📋 View Birth Details"):
    st.markdown(f"""
    **Date:** {birth_data['dob']}  
    **Time:** {birth_data['tob']}  
    **Place:** {birth_data['place']}  
    **Gender:** {birth_data['gender']}
    """)

# ---------- Calculate Comprehensive Chart ----------
if "chart_result" not in st.session_state or submitted:
    with st.spinner("⭐ Calculating comprehensive KP chart..."):
        chart_result, error = calculate_comprehensive_chart(
            birth_data['dob'], 
            birth_data['tob'], 
            birth_data['place']
        )
        
        if error:
            st.error(f"⚠️ {error}")
            st.stop()
        else:
            st.session_state["chart_result"] = chart_result

# Display Chart
st.markdown("### 🌙 Your Complete KP Chart")
with st.container(border=True):
    st.markdown(st.session_state["chart_result"]['display'])

st.info("👇 Get AI interpretations based on your complete chart analysis")

# ---------- AI Agent Prompts ----------
AGENTS = {
    "overall": """You are an expert KP (Krishnamurti Paddhati) astrologer with deep knowledge of Vedic astrology.

You will receive COMPLETE chart data including:
- All 12 house cusps with sub-lords
- All 9 planets with signs, nakshatras, and sub-lords
- Current and upcoming Vimshottari Dasha periods

Use KP principles:
- Sub-lord is the KEY significator (most important)
- Analyze cuspal sub-lords for predictions
- Consider nakshatra lords and planetary positions
- Use dasha periods for timing predictions

Provide:
1. Personality overview (3-4 lines based on Lagna, Moon, Sun)
2. Life themes and karmic patterns
3. Major predictions with timing (using current dasha)
4. Strengths and challenges
5. Practical remedies (mantras, charity, lifestyle)
6. Confidence levels for predictions

Be compassionate, realistic, empowering. Avoid absolute statements.
Include disclaimer at end.""",
    
    "career": """You are a career astrology expert specializing in KP system.

Analyze the complete chart focusing on:
- 10th house cusp sub-lord (primary career indicator)
- 6th house (service/job), 2nd house (wealth)
- Mars, Saturn, Jupiter positions and sub-lords
- Current dasha lord's connection to career houses
- Mercury for communication/business

Provide:
1. Career aptitude and best fields (specific suggestions)
2. Current career phase analysis (based on dasha)
3. Timing for job changes, promotions, business ventures
4. Income potential and growth periods
5. Practical career actions and remedies
6. Confidence levels

Be specific, motivational, actionable. Use dasha timing precisely.""",
    
    "relationship": """You are a relationship astrology expert using KP method.

Analyze focusing on:
- 7th house cusp sub-lord (marriage/partnership)
- Venus position, sign, nakshatra, sub-lord
- 5th house (romance), 11th house (fulfillment)
- Mars for passion, Moon for emotions
- Current dasha impact on relationships

Provide:
1. Relationship patterns and emotional nature
2. Marriage/partnership timing (if unmarried)
3. Compatibility indicators
4. Romance vs long-term relationship prospects
5. Relationship remedies and guidance
6. Confidence levels

Be empathetic, gentle, realistic. Consider gender and context."""
}

# ---------- AI Reading Function ----------
def get_ai_reading(agent_type):
    """Get comprehensive AI interpretation with full chart data"""
    try:
        chart = st.session_state["chart_result"]
        
        # Create detailed chart summary for AI
        planets_summary = "\n".join([
            f"- {name}: {data['sign']} ({data['degree']}) | "
            f"Nakshatra: {data['nakshatra']} (Lord: {data['nakshatra_lord']}) | "
            f"Sub-lord: {data['sublord']}"
            for name, data in chart['planets'].items()
        ])
        
        houses_summary = "\n".join([
            f"- {name}: {data['sign']} | "
            f"Nakshatra: {data['nakshatra']} | "
            f"Sub-lord: {data['sublord']}"
            for name, data in chart['houses'].items()
        ])
        
        chart_summary = f"""
Birth Details:
Date: {birth_data['dob']}
Time: {birth_data['tob']}
Place: {birth_data['place']}
Gender: {birth_data['gender']}

=== PLANETARY POSITIONS (KP) ===
{planets_summary}

=== HOUSE CUSPS (KP Placidus) ===
{houses_summary}

=== VIMSHOTTARI DASHA ===
Current Dasha: {chart['dashas']['current']['lord']} 
Period: {chart['dashas']['current']['start']} to {chart['dashas']['current']['end']}
Upcoming Dasha: {chart['dashas']['upcoming']['lord']} (starts {chart['dashas']['upcoming']['start']})

Please provide detailed KP analysis using the above data.
"""
        
        with st.spinner("🔮 Analyzing your complete chart..."):
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": AGENTS[agent_type]},
                    {"role": "user", "content": chart_summary}
                ],
                max_tokens=1200,
                temperature=0.7,
            )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# ---------- Reading Buttons ----------
st.markdown("---")
st.markdown("## 🔮 Get Comprehensive AI Predictions")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🌟 Overall Life", use_container_width=True):
        result = get_ai_reading("overall")
        st.session_state["overall_result"] = result

with col2:
    if st.button("💼 Career", use_container_width=True):
        result = get_ai_reading("career")
        st.session_state["career_result"] = result

with col3:
    if st.button("💖 Relationship", use_container_width=True):
        result = get_ai_reading("relationship")
        st.session_state["relationship_result"] = result

# Display Results
if "overall_result" in st.session_state:
    st.markdown("### 🌟 Overall Life Reading")
    with st.container(border=True):
        st.markdown(st.session_state["overall_result"])

if "career_result" in st.session_state:
    st.markdown("### 💼 Career Reading")
    with st.container(border=True):
        st.markdown(st.session_state["career_result"])

if "relationship_result" in st.session_state:
    st.markdown("### 💖 Relationship Reading")
    with st.container(border=True):
        st.markdown(st.session_state["relationship_result"])

st.markdown("---")
st.caption("✨ Complete KP Analysis | PySwissEph + OpenAI")
st.caption("⚠️ For guidance only. Not a substitute for professional advice.")
