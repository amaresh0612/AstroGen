import streamlit as st
import os, uuid
from openai import OpenAI
from datetime import datetime, timedelta
import swisseph as swe
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz

# ---------- Setup ----------
st.set_page_config(page_title="🧘‍♂️ AstroGen", page_icon="✨", layout="centered")

st.markdown("""
    <style>
        /* Hide the default assistant avatar (new Streamlit DOM structure) */
        [data-testid="stChatMessageAvatar"] img {
            display: none !important;
        }

        /* Add 🧘‍♂️ emoji instead of the avatar */
        [data-testid="stChatMessageAvatar"][data-testid*="assistant"]::before {
            content: "🧘‍♂️";
            font-size: 26px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        /* Optional: style for user emoji (if you want consistency) */
        [data-testid="stChatMessageAvatar"][data-testid*="user"]::before {
            content: "🙂";
            font-size: 22px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
        /* Hide Streamlit's default bot avatar */
        [data-testid="stChatMessageAvatarIcon"] { display: none !important; }

        /* Header text */
        .astro-header {
            text-align: center;
            color: white;
            font-size: 1.2rem;
            margin-bottom: 0;
        }

        .astro-sub {
            text-align: center;
            color: #ccc;
            font-size: 0.9rem;
            margin-top: 0;
        }

        /* Yogi Baba image styling */
        .baba-img {
            display: block;
            margin: 10px auto;
            border-radius: 50%;
            width: 80px;
            height: 80px;
            border: 2px solid gold;
            box-shadow: 0 0 15px gold;
        }
    </style>
""", unsafe_allow_html=True)

# Custom header with image
st.markdown(
    "<h3 style='text-align:center; color:white;'>🙏 Namaste! 🧘‍♂️ I am Yogi Baba - Your Astrologer</h3>",
    unsafe_allow_html=True
)


api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("🚨 Missing API key in .streamlit/secrets.toml or environment.")
    st.stop()

client = OpenAI(api_key=api_key)


# Initialize session state
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]

if "birth_details" not in st.session_state:
    st.session_state.birth_details = None

# ---------- Comprehensive KP Calculation Functions ----------

def get_coordinates(place):
    """Get latitude and longitude for a place"""
    try:
        # If no country is specified, append ", India" as default
        if ',' not in place:
            place = f"{place}, India"
        
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

def get_house_number_from_degree(degree, house_cusps):
    """Determine which house a planet falls in based on degree"""
    for i in range(12):
        current_cusp = house_cusps[i] % 360
        next_cusp = house_cusps[(i + 1) % 12] % 360
        
        if current_cusp < next_cusp:
            if current_cusp <= degree < next_cusp:
                return i + 1
        else:  # Cusp crosses 0 degrees
            if degree >= current_cusp or degree < next_cusp:
                return i + 1
    return 1  # Default to first house

def create_visual_chart(house_data, planet_data, house_cusps_degrees):
    """Create an enhanced text-based visual representation of the KP chart"""
    # Initialize 12 houses
    houses = {i: [] for i in range(1, 13)}
    
    # Place planets in houses based on their degrees
    for planet_name, planet_info in planet_data.items():
        house_num = get_house_number_from_degree(planet_info['full_degree'], house_cusps_degrees)
        houses[house_num].append(planet_name[:3])  # Use 3-letter abbreviation
    
    # Create enhanced chart layout (North Indian style)
    chart_lines = []
    chart_lines.append("```")
    chart_lines.append("╔" + "═" * 66 + "╗")
    chart_lines.append("║" + " " * 18 + "LAGNA CHART (KP)" + " " * 33 + "║")
    chart_lines.append("╚" + "═" * 66 + "╝")
    chart_lines.append("")
    chart_lines.append("  ┌" + "─" * 15 + "┬" + "─" * 15 + "┬" + "─" * 15 + "┬" + "─" * 15 + "┐")
    
    # Row 1: Houses 12, 1, 2, 3
    h12 = ", ".join(houses[12]) if houses[12] else ""
    h1 = ", ".join(houses[1]) if houses[1] else ""
    h2 = ", ".join(houses[2]) if houses[2] else ""
    h3 = ", ".join(houses[3]) if houses[3] else ""
    
    chart_lines.append(f"  │ {h12:^13} │ {h1:^13} │ {h2:^13} │ {h3:^13} │")
    chart_lines.append(f"  │    [XII]    │     [I]     │    [II]     │    [III]    │")
    chart_lines.append("  ├" + "─" * 15 + "┼" + "─" * 15 + "┼" + "─" * 15 + "┼" + "─" * 15 + "┤")
    
    # Row 2: Houses 11, X, X, 4
    h11 = ", ".join(houses[11]) if houses[11] else ""
    h4 = ", ".join(houses[4]) if houses[4] else ""
    
    chart_lines.append(f"  │ {h11:^13} │             │             │ {h4:^13} │")
    chart_lines.append(f"  │    [XI]     │             │             │    [IV]     │")
    chart_lines.append("  ├" + "─" * 15 + "┤" + " " * 15 + " " + " " * 15 + "├" + "─" * 15 + "┤")
    
    # Row 3: Houses 10, X, X, 5
    h10 = ", ".join(houses[10]) if houses[10] else ""
    h5 = ", ".join(houses[5]) if houses[5] else ""
    
    chart_lines.append(f"  │ {h10:^13} │             │             │ {h5:^13} │")
    chart_lines.append(f"  │     [X]     │             │             │     [V]     │")
    chart_lines.append("  ├" + "─" * 15 + "┼" + "─" * 15 + "┼" + "─" * 15 + "┼" + "─" * 15 + "┤")
    
    # Row 4: Houses 9, 8, 7, 6
    h9 = ", ".join(houses[9]) if houses[9] else ""
    h8 = ", ".join(houses[8]) if houses[8] else ""
    h7 = ", ".join(houses[7]) if houses[7] else ""
    h6 = ", ".join(houses[6]) if houses[6] else ""
    
    chart_lines.append(f"  │ {h9:^13} │ {h8:^13} │ {h7:^13} │ {h6:^13} │")
    chart_lines.append(f"  │    [IX]     │   [VIII]    │    [VII]    │    [VI]     │")
    chart_lines.append("  └" + "─" * 15 + "┴" + "─" * 15 + "┴" + "─" * 15 + "┴" + "─" * 15 + "┘")
    chart_lines.append("```")
    
    return "\n".join(chart_lines)

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
        
        # Store cusp degrees for house placement calculation
        house_cusps_degrees = [cusp % 360 for cusp in house_cusps[:12]]
        
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
        
        # Create visual chart
        visual_chart = create_visual_chart(house_data, planet_data, house_cusps_degrees)
        
        # Create detailed planetary table
        planet_table = "### 🪐 Planetary Positions (Detailed)\n\n"
        planet_table += "| Planet | Sign | Degree | Nakshatra | Nak Lord | Sub-lord |\n"
        planet_table += "|--------|------|--------|-----------|----------|----------|\n"
        for name in ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu', 'Ketu']:
            p = planet_data[name]
            planet_table += f"| **{name}** | {p['sign']} | {p['degree']} | {p['nakshatra']} | {p['nakshatra_lord']} | {p['sublord']} |\n"
        
        # Create house cusps table
        house_table = "\n### 🏠 House Cusps with Sub-lords\n\n"
        house_table += "| House | Sign | Degree | Sub-lord | Significance |\n"
        house_table += "|-------|------|--------|----------|-------------|\n"
        
        house_meanings = {
            '1st (Lagna)': 'Self, Personality',
            '2nd': 'Wealth, Family',
            '3rd': 'Siblings, Courage',
            '4th': 'Mother, Home',
            '5th': 'Children, Romance',
            '6th': 'Health, Service',
            '7th': 'Marriage, Partnership',
            '8th': 'Longevity, Occult',
            '9th': 'Fortune, Father',
            '10th': 'Career, Status',
            '11th': 'Gains, Friends',
            '12th': 'Loss, Spirituality'
        }
        
        for name in house_names:
            h = house_data[name]
            meaning = house_meanings.get(name, '')
            house_table += f"| **{name}** | {h['sign']} | {h['degree']} | {h['sublord']} | {meaning} |\n"
        
        display_text = f"""
{visual_chart}

{planet_table}

{house_table}

### ⏰ Vimshottari Dasha (Planetary Periods)
**Current Dasha:** {dasha_info['current']['lord']} Dasha  
**Period:** {dasha_info['current']['start']} to {dasha_info['current']['end']} ({dasha_info['current']['years']} years)  
**Upcoming:** {dasha_info['upcoming']['lord']} Dasha starts on {dasha_info['upcoming']['start']} ({dasha_info['upcoming']['years']} years)

📍 **Location:** {place} ({lat:.2f}°, {lng:.2f}°)  
🌍 **Ayanamsa:** KP (Krishnamurti)  
🏠 **House System:** Placidus
"""
        
        return {
            'houses': house_data,
            'planets': planet_data,
            'dashas': dasha_info,
            'location': {'place': place, 'lat': lat, 'lng': lng},
            'display': display_text,
            'visual_chart': visual_chart
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
            value=None,
            min_value=datetime(1900, 1, 1).date(),
            max_value=datetime.today().date(),
            format="DD/MM/YYYY"
        )
        place = st.text_input("Place of Birth", value="", placeholder="e.g., Mumbai, India")
    with col2:
        # Time input with 12-hour format
        time_col1, time_col2, time_col3 = st.columns([2, 2, 1])
        with time_col1:
            hour_12 = st.text_input("Hour (1-12)", value="", max_chars=2, placeholder="HH")
        with time_col2:
            minute = st.text_input("Minute (0-59)", value="", max_chars=2, placeholder="MM")
        with time_col3:
            am_pm = st.selectbox("AM/PM", ["AM", "PM"])
        
        gender = st.selectbox("Gender", ["Male", "Female", "Other"])
    
    submitted = st.form_submit_button("Generate Complete KP Chart ✨", use_container_width=True)

if submitted:
    # Validate inputs
    if dob is None:
        st.error("⚠️ Please select a date of birth")
        st.stop()
    if not hour_12.strip() or not minute.strip():
        st.error("⚠️ Please enter both hour and minute")
        st.stop()
    if not place.strip():
        st.error("⚠️ Please enter a place of birth")
        st.stop()
    
    # Validate hour and minute are numeric
    try:
        hour_val = int(hour_12)
        minute_val = int(minute)
        
        if hour_val < 1 or hour_val > 12:
            st.error("⚠️ Hour must be between 1 and 12")
            st.stop()
        if minute_val < 0 or minute_val > 59:
            st.error("⚠️ Minute must be between 0 and 59")
            st.stop()
            
    except ValueError:
        st.error("⚠️ Please enter valid numbers for hour and minute")
        st.stop()
    
    # Convert 12-hour format to 24-hour format
    hour_24 = hour_val if am_pm == "AM" and hour_val != 12 else (0 if am_pm == "AM" and hour_val == 12 else (hour_val if hour_val == 12 else hour_val + 12))
    
    # Convert to time object (24-hour format)
    tob = datetime.strptime(f"{hour_24:02d}:{minute_val:02d}", "%H:%M").time()
    
    # Store time display in 12-hour format
    time_display = f"{hour_val:02d}:{minute_val:02d} {am_pm}"
    
    st.session_state.birth_details = {
        "dob": dob,
        "tob": tob,
        "tob_display": time_display,
        "place": place.strip(),
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
    display_time = birth_data.get('tob_display', birth_data['tob'].strftime('%I:%M %p'))
    st.markdown(f"""
    **Date:** {birth_data['dob']}  
    **Time:** {display_time}  
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

# Add Download Button
def create_downloadable_report():
    """Create a comprehensive text report for download"""
    chart = st.session_state["chart_result"]
    birth = st.session_state["birth_details"]
    
    display_time = birth.get('tob_display', birth['tob'].strftime('%I:%M %p'))
    
    report = f"""
╔═══════════════════════════════════════════════════════════════════╗
                    KP ASTROLOGY CHART REPORT
╚═══════════════════════════════════════════════════════════════════╝

BIRTH DETAILS:
───────────────────────────────────────────────────────────────────
Name/ID: {st.session_state['user_id']}
Date of Birth: {birth['dob']}
Time of Birth: {display_time}
Place of Birth: {birth['place']}
Gender: {birth['gender']}
Location: {chart['location']['lat']}°, {chart['location']['lng']}°

╔═══════════════════════════════════════════════════════════════════╗

{chart.get('visual_chart', '').replace('```', '')}

╚═══════════════════════════════════════════════════════════════════╝

╔═══════════════════════════════════════════════════════════════════╗
                    DETAILED PLANETARY DATA
╚═══════════════════════════════════════════════════════════════════╝

"""
    
    for name in ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu', 'Ketu']:
        p = chart['planets'][name]
        report += f"""
{name.upper()}:
  Sign: {p['sign']}
  Degree: {p['degree']}
  Nakshatra: {p['nakshatra']} (Lord: {p['nakshatra_lord']})
  Sub-lord: {p['sublord']} ⭐ (KP Significator)
"""
    
    report += """
╔═══════════════════════════════════════════════════════════════════╗
                    HOUSE CUSPS ANALYSIS
╚═══════════════════════════════════════════════════════════════════╝
"""
    
    house_meanings = {
        '1st (Lagna)': 'Self, Personality, Physical Body',
        '2nd': 'Wealth, Family, Speech',
        '3rd': 'Siblings, Courage, Communication',
        '4th': 'Mother, Home, Property, Education',
        '5th': 'Children, Romance, Creativity, Speculation',
        '6th': 'Health, Service, Enemies, Debts',
        '7th': 'Marriage, Partnership, Spouse',
        '8th': 'Longevity, Occult, Inheritance, Transformation',
        '9th': 'Fortune, Father, Higher Education, Religion',
        '10th': 'Career, Status, Profession, Reputation',
        '11th': 'Gains, Income, Friends, Desires',
        '12th': 'Loss, Expenses, Spirituality, Foreign Lands'
    }
    
    for house_name in ['1st (Lagna)', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th', '11th', '12th']:
        h = chart['houses'][house_name]
        report += f"""
{house_name} HOUSE - {house_meanings[house_name]}
  Sign: {h['sign']}
  Degree: {h['degree']}
  Nakshatra: {h['nakshatra']}
  Sub-lord: {h['sublord']} ⭐ (Key Significator)
"""
    
    report += f"""
╔═══════════════════════════════════════════════════════════════════╗
                    VIMSHOTTARI DASHA PERIODS
╚═══════════════════════════════════════════════════════════════════╝

CURRENT DASHA:
  Lord: {chart['dashas']['current']['lord']}
  Period: {chart['dashas']['current']['start']} to {chart['dashas']['current']['end']}
  Duration: {chart['dashas']['current']['years']} years

UPCOMING DASHA:
  Lord: {chart['dashas']['upcoming']['lord']}
  Starts: {chart['dashas']['upcoming']['start']}
  Duration: {chart['dashas']['upcoming']['years']} years

╔═══════════════════════════════════════════════════════════════════╗
                    CALCULATION DETAILS
╚═══════════════════════════════════════════════════════════════════╝

Ayanamsa: KP (Krishnamurti)
House System: Placidus
Ephemeris: Swiss Ephemeris
Calculation Engine: PySwissEph

╔═══════════════════════════════════════════════════════════════════╗
                    AI PREDICTIONS
╚═══════════════════════════════════════════════════════════════════╝
"""
    
    # Add AI predictions if available
    if "overall_result" in st.session_state:
        report += f"""
OVERALL LIFE READING:
───────────────────────────────────────────────────────────────────
{st.session_state['overall_result']}

"""
    
    if "career_result" in st.session_state:
        report += f"""
CAREER READING:
───────────────────────────────────────────────────────────────────
{st.session_state['career_result']}

"""
    
    if "relationship_result" in st.session_state:
        report += f"""
RELATIONSHIP READING:
───────────────────────────────────────────────────────────────────
{st.session_state['relationship_result']}

"""
    
    report += f"""
╔═══════════════════════════════════════════════════════════════════╗
                        DISCLAIMER
╚═══════════════════════════════════════════════════════════════════╝

This astrological report is for guidance and entertainment purposes
only. It should not be considered as a substitute for professional
advice in matters of health, finance, legal, or other areas requiring
expert consultation.

Astrology is an interpretive art, and predictions may vary based on
various factors and individual circumstances.

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Report ID: {st.session_state['user_id']}

╔═══════════════════════════════════════════════════════════════════╗
           © AstroGen - KP Astrology Report
╚═══════════════════════════════════════════════════════════════════╝
"""
    
    return report

# Download button
col1, col2 = st.columns([3, 1])
with col2:
    if st.session_state.get("chart_result"):
        report_text = create_downloadable_report()
        st.download_button(
            label="📥 Download Chart",
            data=report_text,
            file_name=f"KP_Chart_{birth_data['dob']}_{st.session_state['user_id']}.txt",
            mime="text/plain",
            use_container_width=True
        )


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
        
        display_time = birth_data.get('tob_display', birth_data['tob'].strftime('%I:%M %p'))
        
        chart_summary = f"""
Birth Details:
Date: {birth_data['dob']}
Time: {display_time}
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


# --- Add Yogi Baba Avatar + Section ---
baba_svg = """
<svg width="40" height="40" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<circle cx="12" cy="12" r="11" stroke="orange" stroke-width="1.5"/>
<path d="M8 15c1-3 7-3 8 0M10 9a2 2 0 1 0 0.001-4.001A2 2 0 0 0 10 9zm4 0a2 2 0 1 0 0.001-4.001A2 2 0 0 0 14 9z" stroke="orange" stroke-width="1.2"/>
<path d="M6 18c2 2 10 2 12 0" stroke="orange" stroke-width="1.2"/>
</svg>
"""


# --- Initialize chat messages ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "🧘‍♂️ Hello! I am ready 😊 I have now seen all your stars — ask me anything about your destiny."}
    ]

# --- Show previous messages ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Chat input ---
if prompt := st.chat_input("Ask Yogi Baba about your chart..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Build contextual prompt from your existing variables
    chart = st.session_state["chart_result"]

    def safe_get(section, key, default="Not available"):
        try:
            return chart[section].get(key, default)
        except Exception:
            return default

    # Gather key data
    current_date = datetime.now().strftime("%B %d, %Y")
    dob = birth_data['dob']
    tob_display = birth_data.get('tob_display', birth_data['tob'].strftime('%I:%M %p'))
    place = birth_data['place']
    gender = birth_data['gender']

    # Create readable chart summaries
    house_summary = "\n".join([
        f"- {name}: {data['sign']} | Sub-lord: {data['sublord']}"
        for name, data in chart['houses'].items()
    ])

    planet_summary = "\n".join([
        f"- {name}: {data['sign']} ({data['nakshatra']}) | Sub-lord: {data['sublord']}"
        for name, data in chart['planets'].items()
    ])

    dasha = chart['dashas']
    current_dasha = dasha['current']['lord'] if dasha['current'] else "Not available"
    upcoming_dasha = dasha['upcoming']['lord'] if dasha['upcoming'] else "Not available"

    # Combine all into a neat context block
    context = f"""
📅 Current Date: {current_date}

🌙 Birth Details:
Date of Birth: {dob}
Time of Birth: {tob_display}
Place of Birth: {place}
Gender: {gender}

🏠 House Cusps:
{house_summary}

🪐 Planetary Positions:
{planet_summary}

⏰ Vimshottari Dasha:
Current Dasha: {current_dasha}
Upcoming Dasha: {upcoming_dasha}
"""


    # --- Query GPT ---
    with st.chat_message("assistant"):
        with st.spinner("🔮 Consulting the stars..."):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are Yogi Baba, a kind KP astrologer who gives wise and gentle advice."},
                        {"role": "user", "content": context + "\n\nUser Question: " + prompt},
                    ],
                    max_tokens=800,
                    temperature=0.7,
                )
                reply = response.choices[0].message.content.strip()
            except Exception as e:
                reply = f"⚠️ Error: {e}"

            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})

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

st.markdown(
    """
    <div style='
        position: fixed;
        bottom: 10px;
        left: 0;
        width: 100%;
        text-align: center;
        color: #bbb;
        font-size: 13px;
        background-color: rgba(0, 0, 0, 0);
        padding: 5px 0;
        z-index: 9999;
    '>
        ⚠️ For guidance only. Not a substitute for professional advice.
    </div>
    """,
    unsafe_allow_html=True
)