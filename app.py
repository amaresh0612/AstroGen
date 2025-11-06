import streamlit as st
import os, uuid, io
from openai import OpenAI
from datetime import datetime, timedelta
import swisseph as swe
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.graphics.shapes import Drawing, Rect, Line, String
from reportlab.graphics import renderPM

# ---------- Setup ----------
st.set_page_config(page_title="🧘‍♂️ AstroGen", page_icon="✨", layout="centered")

st.markdown("""
    <style>
        [data-testid="stChatMessageAvatar"] img { display: none !important; }
        [data-testid="stChatMessageAvatar"][data-testid*="assistant"]::before {
            content: "🧘‍♂️"; font-size: 26px; display: flex;
            align-items: center; justify-content: center;
        }
        [data-testid="stChatMessageAvatar"][data-testid*="user"]::before {
            content: "🙂"; font-size: 22px; display: flex;
            align-items: center; justify-content: center;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h3 style='text-align:center; color:white;'>🙏 Namaste! 🧘‍♂️ I am Yogi Baba - Your Astrologer</h3>", unsafe_allow_html=True)

api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("🚨 Missing API key")
    st.stop()

client = OpenAI(api_key=api_key)

# Initialize session state
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]
if "birth_details" not in st.session_state:
    st.session_state.birth_details = None

# ---------- KP Calculation Functions ----------

def get_coordinates(place):
    try:
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
    signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
             'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
    sign_num = int(degree / 30)
    degree_in_sign = degree % 30
    return signs[sign_num], degree_in_sign

def get_nakshatra_info(degree):
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
    dasha_lords = ['Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury']
    dasha_years = [7, 20, 6, 10, 7, 18, 16, 19, 17]
    nak_num = int(moon_degree / 13.333333) % 27
    nak_lord_index = nak_num % 9
    nak_completed = (moon_degree % 13.333333) / 13.333333
    first_dasha_balance = dasha_years[nak_lord_index] * (1 - nak_completed)

    dashas = []
    current_date = birth_date
    dashas.append({
        'lord': dasha_lords[nak_lord_index],
        'start': current_date,
        'years': first_dasha_balance,
        'end': current_date + timedelta(days=365.25 * first_dasha_balance)
    })
    current_date = dashas[-1]['end']

    for i in range(1, 10):
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
    for i, dasha in enumerate(dashas):
        if dasha['start'] <= current_date <= dasha['end']:
            current = dasha
            upcoming = dashas[i + 1] if i + 1 < len(dashas) else None
            return current, upcoming
    return None, None

def get_house_number_from_degree(degree, house_cusps):
    for i in range(12):
        current_cusp = house_cusps[i] % 360
        next_cusp = house_cusps[(i + 1) % 12] % 360
        if current_cusp < next_cusp:
            if current_cusp <= degree < next_cusp:
                return i + 1
        else:
            if degree >= current_cusp or degree < next_cusp:
                return i + 1
    return 1

def calculate_comprehensive_chart(dob, tob, place):
    try:
        lat, lng = get_coordinates(place)
        if lat is None or lng is None:
            return None, "Could not find location. Try format: 'Mumbai, India'"

        dt = datetime.combine(dob, tob)
        tz_offset = get_timezone_offset(lat, lng, dt)
        utc_dt = dt - timedelta(hours=tz_offset)
        jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day,
                        utc_dt.hour + utc_dt.minute/60.0)
        swe.set_sid_mode(swe.SIDM_KRISHNAMURTI)

        planet_data = {}
        planets = {
            'Sun': swe.SUN, 'Moon': swe.MOON, 'Mars': swe.MARS,
            'Mercury': swe.MERCURY, 'Jupiter': swe.JUPITER,
            'Venus': swe.VENUS, 'Saturn': swe.SATURN, 'Rahu': swe.MEAN_NODE,
        }

        for name, planet_id in planets.items():
            pos = swe.calc_ut(jd, planet_id, swe.FLG_SIDEREAL)[0]
            degree = pos[0] % 360
            sign, deg_in_sign = get_sign_name(degree)
            nak, nak_lord = get_nakshatra_info(degree)
            sublord = get_sublord(degree)
            planet_data[name] = {
                'sign': sign, 'degree': f"{deg_in_sign:.2f}°",
                'nakshatra': nak, 'nakshatra_lord': nak_lord,
                'sublord': sublord, 'full_degree': degree
            }

        # Add Ketu (opposite Rahu)
        rahu_deg = planet_data['Rahu']['full_degree']
        ketu_deg = (rahu_deg + 180) % 360
        sign, deg_in_sign = get_sign_name(ketu_deg)
        nak, nak_lord = get_nakshatra_info(ketu_deg)
        sublord = get_sublord(ketu_deg)
        planet_data['Ketu'] = {
            'sign': sign, 'degree': f"{deg_in_sign:.2f}°",
            'nakshatra': nak, 'nakshatra_lord': nak_lord,
            'sublord': sublord, 'full_degree': ketu_deg
        }

        houses_calc = swe.houses(jd, lat, lng, b'P')
        house_cusps = houses_calc[0]
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
                'sign': sign, 'degree': f"{deg_in_sign:.2f}°",
                'nakshatra': nak, 'nakshatra_lord': nak_lord,
                'sublord': sublord
            }

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

        return {
            'houses': house_data,
            'planets': planet_data,
            'dashas': dasha_info,
            'location': {'place': place, 'lat': lat, 'lng': lng},
            'house_cusps_degrees': house_cusps_degrees
        }, None

    except Exception as e:
        return None, f"Error: {str(e)}"

# ---------- East-Indian Chart (UI + PDF) ----------

def _planet_abbr(name: str) -> str:
    # 3-letter, all caps; common short forms
    mapping = {
        'Sun': 'SUN', 'Moon': 'MOO', 'Mars': 'MAR', 'Mercury': 'MER',
        'Jupiter': 'JUP', 'Venus': 'VEN', 'Saturn': 'SAT',
        'Rahu': 'RAH', 'Ketu': 'KET'
    }
    return mapping.get(name, name[:3].upper())


def create_east_indian_chart_drawing(planet_data, house_cusps_degrees):
    """
    Clean East-Indian 3×3 grid with corner triangles.
    Top-left diagonal runs from top-left -> bottom-right (↘).
    All diagonals and borders are black.
    """
    size = 440
    margin = 24
    inner = size - 2 * margin
    cell = inner / 3.0

    d = Drawing(size, size)

    # Outer frame
    d.add(Rect(6, 6, size - 12, size - 12,
               strokeColor=colors.black,
               fillColor=None, strokeWidth=6))

    # Inner square
    ox, oy = margin, margin
    d.add(Rect(ox, oy, inner, inner,
               strokeColor=colors.black, fillColor=None, strokeWidth=2))

    # 3×3 grid
    for i in range(1, 3):
        d.add(Line(ox + i * cell, oy, ox + i * cell, oy + inner,
                   strokeColor=colors.black, strokeWidth=1.5))
        d.add(Line(ox, oy + i * cell, ox + inner, oy + i * cell,
                   strokeColor=colors.black, strokeWidth=1.5))

    # Coordinates for corners
    x0, x1, x2, x3 = ox, ox + cell, ox + 2 * cell, ox + 3 * cell
    y0, y1, y2, y3 = oy, oy + cell, oy + 2 * cell, oy + 3 * cell

    # Diagonals (all black, correct East-Indian orientation)
    d.add(Line(x0, y3, x1, y2, strokeColor=colors.black, strokeWidth=1.5))  # top-left ↘
    d.add(Line(x3, y3, x2, y2, strokeColor=colors.black, strokeWidth=1.5))  # top-right ↙
    d.add(Line(x0, y0, x1, y1, strokeColor=colors.black, strokeWidth=1.5))  # bottom-left ↗
    d.add(Line(x3, y0, x2, y1, strokeColor=colors.black, strokeWidth=1.5))  # bottom-right ↖

    # Planet text positions (same as before)
    positions = {
        1:  (ox + 1.50*cell, oy + 2.68*cell, 'middle'),
        2:  (ox + 2.73*cell, oy + 2.18*cell, 'end'),
        3:  (ox + 2.73*cell, oy + 1.50*cell, 'end'),
        4:  (ox + 2.73*cell, oy + 0.32*cell, 'end'),
        5:  (ox + 1.50*cell, oy + 0.32*cell, 'middle'),
        6:  (ox + 1.50*cell, oy + 1.50*cell, 'middle'),
        7:  (ox + 0.27*cell, oy + 1.50*cell, 'start'),
        8:  (ox + 0.27*cell, oy + 2.18*cell, 'start'),
        9:  (ox + 1.50*cell, oy + 2.18*cell, 'middle'),
        10: (ox + 0.27*cell, oy + 0.32*cell, 'start'),
        11: (ox + 0.27*cell, oy + 1.82*cell, 'start'),
        12: (ox + 0.80*cell, oy + 2.80*cell, 'middle'),
    }

    # Assign planets to houses
    houses = {i: [] for i in range(1, 13)}
    for pname, pdata in planet_data.items():
        hnum = get_house_number_from_degree(pdata['full_degree'], house_cusps_degrees)
        houses[hnum].append(_planet_abbr(pname))

    # Draw planet abbreviations in each house
    for h in range(1, 13):
        x, y, anchor = positions.get(h, (ox + 1.5*cell, oy + 1.5*cell, 'middle'))
        if houses[h]:
            text = ", ".join(houses[h])
            font_size = 11 if len(text) < 12 else 9
            d.add(String(x, y, text, fontSize=font_size,
                         fillColor=colors.darkblue, textAnchor=anchor,
                         fontName="Helvetica-Bold"))
    return d


# ---------- PDF Generation ----------

def generate_pdf_report(birth_data, chart_data):
    """Generate a professional PDF report (with the exact same East-Indian chart image)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    styles = getSampleStyleSheet()

    # Styles
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
                                 fontSize=24, textColor=colors.HexColor('#8B4513'),
                                 alignment=TA_CENTER, spaceAfter=12)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'],
                                   fontSize=14, textColor=colors.HexColor('#FF8C00'),
                                   spaceAfter=10, spaceBefore=12)

    # Title
    story.append(Paragraph("🙏 KP ASTROLOGY CHART REPORT", title_style))
    story.append(Spacer(1, 0.2*inch))

    # Birth Details
    story.append(Paragraph("Birth Details", heading_style))
    birth_table_data = [
        ["Date of Birth:", str(birth_data['dob'])],
        ["Time of Birth:", birth_data.get('tob_display', birth_data['tob'].strftime('%I:%M %p'))],
        ["Place of Birth:", birth_data['place']],
        ["Gender:", birth_data['gender']],
        ["Coordinates:", f"{chart_data['location']['lat']:.2f}°, {chart_data['location']['lng']:.2f}°"]
    ]
    birth_table = Table(birth_table_data, colWidths=[2*inch, 4*inch])
    birth_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#FFF8DC')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(birth_table)
    story.append(Spacer(1, 0.3*inch))

    # East Indian Chart (render to PNG then embed)
    story.append(Paragraph("Lagna Chart (East Indian Style)", heading_style))
    chart_drawing = create_east_indian_chart_drawing(chart_data['planets'],
                                                     chart_data['house_cusps_degrees'])
    try:
        png_bytes = renderPM.drawToString(chart_drawing, fmt='PNG')
        img_io = io.BytesIO(png_bytes)
        img = RLImage(img_io, width=4.8*inch, height=4.8*inch)
        story.append(img)
    except Exception:
        # fallback: vector drawing if renderPM/Pillow is missing
        story.append(chart_drawing)
    story.append(Spacer(1, 0.3*inch))

    # Planetary Positions
    story.append(Paragraph("Planetary Positions (KP)", heading_style))
    planet_table_data = [["Planet", "Sign", "Degree", "Nakshatra", "Nak Lord", "Sub-lord"]]
    for name in ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu', 'Ketu']:
        p = chart_data['planets'][name]
        planet_table_data.append([name, p['sign'], p['degree'],
                                  p['nakshatra'], p['nakshatra_lord'], p['sublord']])
    planet_table = Table(planet_table_data, colWidths=[1*inch, 1*inch, 1*inch, 1.5*inch, 1*inch, 1*inch])
    planet_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF8C00')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FFF8DC')]),
    ]))
    story.append(planet_table)
    story.append(PageBreak())

    # House cusps table
    story.append(Paragraph("House Cusps with Sub-lords", heading_style))
    house_meanings = {
        '1st (Lagna)': 'Self, Personality', '2nd': 'Wealth, Family',
        '3rd': 'Siblings, Courage', '4th': 'Mother, Home',
        '5th': 'Children, Romance', '6th': 'Health, Service',
        '7th': 'Marriage, Partnership', '8th': 'Longevity, Occult',
        '9th': 'Fortune, Father', '10th': 'Career, Status',
        '11th': 'Gains, Friends', '12th': 'Loss, Spirituality'
    }
    house_table_data = [["House", "Sign", "Degree", "Sub-lord", "Significance"]]
    house_names = ['1st (Lagna)', '2nd', '3rd', '4th', '5th', '6th',
                   '7th', '8th', '9th', '10th', '11th', '12th']
    for name in house_names:
        h = chart_data['houses'][name]
        house_table_data.append([name, h['sign'], h['degree'], h['sublord'], house_meanings[name]])
    house_table = Table(house_table_data, colWidths=[1*inch, 1*inch, 1*inch, 1*inch, 2.5*inch])
    house_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8B4513')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FFF8DC')]),
    ]))
    story.append(house_table)
    story.append(Spacer(1, 0.3*inch))

    # Dasha Information
    story.append(Paragraph("Vimshottari Dasha Periods", heading_style))
    dasha = chart_data['dashas']
    if dasha['current']:
        dasha_text = f"""
        <b>Current Dasha:</b> {dasha['current']['lord']} Dasha<br/>
        <b>Period:</b> {dasha['current']['start']} to {dasha['current']['end']} 
        ({dasha['current']['years']} years)<br/>
        <b>Upcoming:</b> {dasha['upcoming']['lord']} Dasha starts on 
        {dasha['upcoming']['start']} ({dasha['upcoming']['years']} years)
        """
        story.append(Paragraph(dasha_text, styles['Normal']))

    # Disclaimer
    story.append(Spacer(1, 0.3*inch))
    disclaimer = """
    <para align=center><i>
    This astrological report is for guidance and entertainment purposes only.<br/>
    Not a substitute for professional advice in health, finance, legal, or other areas.<br/>
    Generated: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """
    </i></para>
    """
    story.append(Paragraph(disclaimer, styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ---------- Birth Details Form ----------
# ----- Professional-looking birth-details form (replace your old form block) -----
st.markdown(
    """
    <style>
    /* Card */
    .card {
        background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(0,0,0,0.02));
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.35);
        border: 1px solid rgba(255,255,255,0.04);
        margin-bottom: 18px;
    }
    .card h2 {
        margin: 0 0 6px 0;
        font-size: 20px;
        color: #ffb74d;
    }
    .card .muted {
        color: #bdbdbd;
        margin-bottom: 18px;
        font-size: 13px;
    }

    /* Input styling (applies to text inputs) */
    .stTextInput>div>div>input, .stTextInput>div>div>textarea {
        background: rgba(255,255,255,0.02) !important;
        border-radius: 8px !important;
        padding: 14px 12px !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        color: #e6e6e6 !important;
        font-size: 15px !important;
    }

    /* Selectbox styling */
    .stSelectbox>div>div>div>div, .stMultiSelect>div>div>div>div {
        border-radius: 8px !important;
        padding: 8px 10px !important;
        background: rgba(255,255,255,0.02) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        color: #e6e6e6;
        font-size: 15px;
    }

    /* Radio button spacing */
    .stRadio .css-1r6slb0 { gap: 12px; }

    /* Submit button style */
    div.stButton > button:first-child {
        background-color: #ff8c00;
        color: white;
        padding: 12px 20px;
        border-radius: 10px;
        font-weight: 600;
        font-size: 15px;
        border: none;
    }
    div.stButton > button:first-child:hover {
        background-color: #ff9f33;
        transform: translateY(-1px);
    }
    </style>
    """,
    unsafe_allow_html=True
)

# card wrapper (visual only)
st.markdown('<div class="card"><h2>Enter your birth details</h2><div class="muted">Provide accurate date, time and place for best results</div></div>', unsafe_allow_html=True)

with st.form("birth_form", clear_on_submit=False):
    # Use two columns: left for date/place, right for time/gender
    left_col, right_col = st.columns([2, 1.15], gap="medium")

    # LEFT: Date and Place
    with left_col:
        dob_str = st.text_input(
            "Date of Birth (DD/MM/YYYY)",
            value="",
            placeholder="e.g., 23/09/1994",
            help="Enter date in format DD/MM/YYYY"
        )
        place = st.text_input(
            "Place of Birth",
            value="",
            placeholder="e.g., Mumbai, India",
            help="City, Country (for geocoding)"
        )

    # RIGHT: Time inputs and gender
    with right_col:
        st.write("**Time of Birth**")
        tcols = st.columns([1.1, 1.1, 1.2], gap="small")
        hour_12 = tcols[0].text_input("Hour (1-12)", value="", max_chars=2, placeholder="HH")
        minute = tcols[1].text_input("Minute (0-59)", value="", max_chars=2, placeholder="MM")
        am_pm = tcols[2].radio("", ["AM", "PM"], horizontal=True)

        st.write("")  # spacer
        gender = st.selectbox("Gender", ["Male", "Female", "Other"])

    # Validation helper (just for UX; final checks below on submit)
    def _validated_date(s):
        from datetime import datetime
        s = s.strip()
        if not s:
            return None
        try:
            return datetime.strptime(s, "%d/%m/%Y").date()
        except Exception:
            return None

    submitted = st.form_submit_button("Generate Complete KP Chart ✨")

    # Process submission (in-form so validation messages appear immediately)
    if submitted:
        dob = _validated_date(dob_str)
        if dob is None:
            st.error("⚠️ Enter a valid date in DD/MM/YYYY format (for example: 23/09/1994).")
        else:
            # Validate time values
            try:
                h = int(hour_12)
                m = int(minute)
                if not (1 <= h <= 12) or not (0 <= m <= 59):
                    raise ValueError()
            except Exception:
                st.error("⚠️ Enter valid time: hour 1-12 and minute 0-59.")
                dob = None

        # If all OK, store values in session and continue
        if dob is not None:
            # convert to 24-hour
            hour_24 = h if (am_pm == "AM" and h != 12) else (0 if (am_pm == "AM" and h == 12) else (h if h == 12 else h + 12))
            tob = datetime.strptime(f"{hour_24:02d}:{m:02d}", "%H:%M").time()
            time_display = f"{int(hour_12):02d}:{int(minute):02d} {am_pm}"

            st.session_state.birth_details = {
                "dob": dob,
                "tob": tob,
                "tob_display": time_display,
                "place": place.strip(),
                "gender": gender
            }
            st.success("✅ Birth details captured — generating chart...")


if submitted:
    if dob is None or not hour_12.strip() or not minute.strip() or not place.strip():
        st.error("⚠️ Please fill all fields")
        st.stop()
    try:
        hour_val = int(hour_12)
        minute_val = int(minute)
        if not (1 <= hour_val <= 12) or not (0 <= minute_val <= 59):
            st.error("⚠️ Invalid time values")
            st.stop()
    except ValueError:
        st.error("⚠️ Please enter valid numbers")
        st.stop()

    hour_24 = hour_val if am_pm == "AM" and hour_val != 12 else (0 if am_pm == "AM" and hour_val == 12 else (hour_val if hour_val == 12 else hour_val + 12))
    tob = datetime.strptime(f"{hour_24:02d}:{minute_val:02d}", "%H:%M").time()
    time_display = f"{hour_val:02d}:{minute_val:02d} {am_pm}"

    st.session_state.birth_details = {
        "dob": dob, "tob": tob, "tob_display": time_display,
        "place": place.strip(), "gender": gender
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
    st.markdown(
        f"""
**Date:** {birth_data['dob']}  
**Time:** {display_time}  
**Place:** {birth_data['place']}  
**Gender:** {birth_data['gender']}
"""
    )

# ---------- Calculate Chart ----------
if "chart_result" not in st.session_state or submitted:
    with st.spinner("⭐ Calculating comprehensive KP chart..."):
        chart_result, error = calculate_comprehensive_chart(
            birth_data['dob'], birth_data['tob'], birth_data['place']
        )
        if error:
            st.error(f"⚠️ {error}")
            st.stop()
        else:
            st.session_state["chart_result"] = chart_result

chart = st.session_state["chart_result"]

# ---------- East-Indian Chart (UI)
st.markdown("### 🌙 Your Complete KP Chart")
with st.container(border=True):
    st.markdown("#### East Indian Chart")
    # Render the drawing to PNG and show in UI so it matches PDF exactly
    drawing = create_east_indian_chart_drawing(chart['planets'], chart['house_cusps_degrees'])
    try:
        png = renderPM.drawToString(drawing, fmt='PNG')
        st.image(png)
    except Exception:
        # fallback to simple text table if renderPM not present
        st.info("Image renderer not available; showing text layout.")
        houses = {i: [] for i in range(1, 13)}
        for planet_name, planet_info in chart['planets'].items():
            house_num = get_house_number_from_degree(planet_info['full_degree'], chart['house_cusps_degrees'])
            houses[house_num].append(_planet_abbr(planet_name))
        st.write(houses)

# Planetary Positions Table
with st.expander("🪐 Planetary Positions (Detailed)", expanded=False):
    rows = []
    for name in ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu', 'Ketu']:
        p = chart['planets'][name]
        rows.append({
            'Planet': name, 'Sign': p['sign'], 'Degree': p['degree'],
            'Nakshatra': p['nakshatra'], 'Nak Lord': p['nakshatra_lord'], 'Sub-lord': p['sublord']
        })
    st.table(rows)

# House Cusps Table
with st.expander("🏠 House Cusps with Sub-lords", expanded=False):
    house_meanings = {
        '1st (Lagna)': 'Self, Personality', '2nd': 'Wealth, Family',
        '3rd': 'Siblings, Courage', '4th': 'Mother, Home',
        '5th': 'Children, Romance', '6th': 'Health, Service',
        '7th': 'Marriage, Partnership', '8th': 'Longevity, Occult',
        '9th': 'Fortune, Father', '10th': 'Career, Status',
        '11th': 'Gains, Friends', '12th': 'Loss, Spirituality'
    }
    rows = []
    for name in ['1st (Lagna)', '2nd', '3rd', '4th', '5th', '6th',
                 '7th', '8th', '9th', '10th', '11th', '12th']:
        h = chart['houses'][name]
        rows.append({'House': name, 'Sign': h['sign'], 'Degree': h['degree'],
                     'Sub-lord': h['sublord'], 'Significance': house_meanings[name]})
    st.table(rows)

# Dasha Information
with st.expander("⏰ Vimshottari Dasha", expanded=False):
    dasha = chart['dashas']
    if dasha['current']:
        st.markdown(
            f"""
**Current Dasha:** {dasha['current']['lord']} Dasha  
**Period:** {dasha['current']['start']} to {dasha['current']['end']} ({dasha['current']['years']} years)  
**Upcoming:** {dasha['upcoming']['lord']} Dasha starts on {dasha['upcoming']['start']} ({dasha['upcoming']['years']} years)
"""
        )

# ---------- Single-click PDF Download ----------
st.markdown("---")
col1, col2 = st.columns([3, 1])
with col2:
    try:
        pdf_buffer = generate_pdf_report(birth_data, chart)
        st.download_button(
            label="📥 Download PDF",
            data=pdf_buffer.getvalue(),
            file_name=f"KP_Chart_{birth_data['dob']}_{st.session_state['user_id']}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    except Exception as e:
        st.error(f"⚠️ PDF generation error: {e}")

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

def get_ai_reading(agent_type):
    try:
        chart = st.session_state["chart_result"]
        planets_summary = "\n".join([
            f"- {name}: {data['sign']} ({data['degree']}) | "
            f"Nakshatra: {data['nakshatra']} (Lord: {data['nakshatra_lord']}) | "
            f"Sub-lord: {data['sublord']}"
            for name, data in chart['planets'].items()
        ])
        houses_summary = "\n".join([
            f"- {name}: {data['sign']} | Nakshatra: {data['nakshatra']} | Sub-lord: {data['sublord']}"
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

# ---------- AI Readings UI ----------
st.markdown("---")
st.markdown("### 🔮 AI Astrological Readings")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🌟 Overall Life", use_container_width=True):
        st.session_state["overall_result"] = get_ai_reading("overall")
with col2:
    if st.button("💼 Career", use_container_width=True):
        st.session_state["career_result"] = get_ai_reading("career")
with col3:
    if st.button("💖 Relationship", use_container_width=True):
        st.session_state["relationship_result"] = get_ai_reading("relationship")

if "overall_result" in st.session_state:
    st.markdown("#### 🌟 Overall Life Reading")
    with st.container(border=True):
        st.markdown(st.session_state["overall_result"])

if "career_result" in st.session_state:
    st.markdown("#### 💼 Career Reading")
    with st.container(border=True):
        st.markdown(st.session_state["career_result"])

if "relationship_result" in st.session_state:
    st.markdown("#### 💖 Relationship Reading")
    with st.container(border=True):
        st.markdown(st.session_state["relationship_result"])

# ---------- Chat ----------
st.markdown("---")
st.markdown("### 💬 Ask Yogi Baba")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "🧘‍♂️ Hello! I am ready 😊 I have now seen all your stars — ask me anything about your destiny."}
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask Yogi Baba about your chart..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    chart = st.session_state["chart_result"]
    current_date = datetime.now().strftime("%B %d, %Y")

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

    context = f"""
📅 Current Date: {current_date}

🌙 Birth Details:
Date of Birth: {birth_data['dob']}
Time of Birth: {birth_data.get('tob_display', birth_data['tob'].strftime('%I:%M %p'))}
Place of Birth: {birth_data['place']}
Gender: {birth_data['gender']}

🏠 House Cusps:
{house_summary}

🪐 Planetary Positions:
{planet_summary}

⏰ Vimshottari Dasha:
Current Dasha: {current_dasha}
Upcoming Dasha: {upcoming_dasha}
"""

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

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #bbb; font-size: 13px; padding: 10px 0;'>
        ⚠️ For guidance only. Not a substitute for professional advice.
    </div>
    """,
    unsafe_allow_html=True
)
