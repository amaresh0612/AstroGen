# app.py (FIXED VERSION - Aligned with reference calculations)
import streamlit as st
from openai import OpenAI
import os, uuid, io
from datetime import datetime, timedelta
import swisseph as swe
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from PIL import Image, ImageDraw, ImageFont
import math
import pandas as pd

st.set_page_config(page_title="🧘‍♂️ AstroGen", page_icon="✨", layout="centered")
THEME_CSS = r"""
<style>
:root{
  /* Light-mode friendly defaults */
  --bg: linear-gradient(180deg,#fbfcfe,#f3f6fb);
  --page-bg-solid: #f6f7f9;
  --card-bg: rgba(255,255,255,0.96);
  --muted: #4b5563;
  --text: #0b1220;
  --accent: #ff8c00;
  --input-bg: rgba(11,18,32,0.03);
  --input-border: rgba(11,18,32,0.08);
  --panel-shadow: 0 6px 18px rgba(11,18,32,0.06);
  --line: rgba(11,18,32,0.12);
}

/* Dark-mode adjustments: purposely not pure black to preserve soft contrast */
@media (prefers-color-scheme: dark) {
  :root{
    --bg: linear-gradient(180deg,#071026,#081426);
    --page-bg-solid: #071026;
    --card-bg: rgba(255,255,255,0.02);
    --muted: #9aa7bd;
    --text: #e6eef8;
    --accent: #ffb64d;
    --input-bg: rgba(255,255,255,0.02);
    --input-border: rgba(255,255,255,0.04);
    --panel-shadow: 0 6px 18px rgba(0,0,0,0.55);
    --line: rgba(255,255,255,0.06);
  }
}

/* App root: keep a soft background instead of full black */
[data-testid='stAppViewContainer'] > .main {
  background: var(--bg) !important;
  color: var(--text) !important;
  padding-top: 12px;
}

/* Header/title (explicit styling so it remains visible) */
.app-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 10px 6px;
  background: transparent;
  border-radius: 10px;
  color: var(--text);
}
.app-header h1 {
  margin: 0; font-size: 18px; font-weight:700; color: var(--accent);
}
.app-header p { margin: 0; color: var(--muted); font-size: 13px; }

/* Chat avatar replacements kept but colors use variables */
[data-testid="stChatMessageAvatar"] img { display: none !important; }
[data-testid="stChatMessageAvatar"][data-testid*="assistant"]::before {
    content: "🧘‍♂️"; font-size: 26px; display: flex;
    align-items: center; justify-content: center; color: var(--accent);
}
[data-testid="stChatMessageAvatar"][data-testid*="user"]::before {
    content: "🙂"; font-size: 22px; display: flex;
    align-items: center; justify-content: center; color: var(--muted);
}

/* Card / panel styling */
.card {
    background: var(--card-bg) !important;
    border-radius: 12px;
    padding: 18px;
    box-shadow: var(--panel-shadow);
    border: 1px solid var(--input-border);
    margin-bottom: 18px;
    color: var(--text);
}
.card h2 { margin: 0 0 6px 0; font-size: 20px; color: var(--accent); }
.card .muted { color: var(--muted); margin-bottom: 12px; font-size: 13px; }

/* Inputs and selects */
.stTextInput>div>div>input, .stTextInput>div>div>textarea,
.stSelectbox>div>div>div>div, .stMultiSelect>div>div>div>div {
    background: var(--input-bg) !important;
    border-radius: 8px !important;
    padding: 12px 12px !important;
    border: 1px solid var(--input-border) !important;
    color: var(--text) !important;
    font-size: 15px !important;
}

/* Buttons */
div.stButton > button:first-child {
    background-color: var(--accent) !important;
    color: white !important;
    padding: 10px 18px !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    border: none !important;
}
div.stButton > button:first-child:hover { transform: translateY(-1px); }

/* Table / small text */
.stTable td, .stTable th, .stCheckbox, .stMarkdown {
    color: var(--text) !important;
}

/* Footer / caption */
footer, .stCaption, .stText {
    color: var(--muted) !important;
}

/* Chart image */
img { max-width: 100% !important; height: auto !important; }

/* subtle dividers */
hr, .css-1v3fvcr { border-color: var(--line) !important; }

/* small text tweaks */
.canvas-legend, .chart-note { color: var(--muted) !important; }
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

# ---------- Restored header (visible in both themes) ----------
st.markdown(
    """
    <div class="app-header">
      <h1>🙏 Namaste! 🧘‍♂️ I am Yogi Baba - Your Astrologer</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

# ensure submitted always exists
submitted = False

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


# ========== CRITICAL FIX: Use KP Ayanamsa (not Lahiri) ==========
try:
    # KP uses its own ayanamsa calculation
    swe.set_sid_mode(swe.SIDM_KRISHNAMURTI)
except Exception:
    pass

# ---------- Config ----------
CHITRAPAKSHA_AYANAMSA_DEG = 24.0166666667 # 24°01'00" - Chitrapaksha standard
SIGNS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']
SIGN_RULERS = {
    'Aries': 'Mars', 'Taurus': 'Venus', 'Gemini': 'Mercury', 'Cancer': 'Moon',
    'Leo': 'Sun', 'Virgo': 'Mercury', 'Libra': 'Venus', 'Scorpio': 'Mars',
    'Sagittarius': 'Jupiter', 'Capricorn': 'Saturn', 'Aquarius': 'Saturn', 'Pisces': 'Jupiter'
}
NAKSHATRAS = [
    ('Ashwini','Ketu'), ('Bharani','Venus'), ('Krittika','Sun'),
    ('Rohini','Moon'), ('Mrigashira','Mars'), ('Ardra','Rahu'),
    ('Punarvasu','Jupiter'), ('Pushya','Saturn'), ('Ashlesha','Mercury'),
    ('Magha','Ketu'), ('Purva Phalguni','Venus'), ('Uttara Phalguni','Sun'),
    ('Hasta','Moon'), ('Chitra','Mars'), ('Swati','Rahu'),
    ('Vishakha','Jupiter'), ('Anuradha','Saturn'), ('Jyeshtha','Mercury'),
    ('Mula','Ketu'), ('Purva Ashadha','Venus'), ('Uttara Ashadha','Sun'),
    ('Shravana','Moon'), ('Dhanishta','Mars'), ('Shatabhisha','Rahu'),
    ('Purva Bhadrapada','Jupiter'), ('Uttara Bhadrapada','Saturn'), ('Revati','Mercury')
]

# ---------- FIXED KP SUBLORD WITH CORRECT BOUNDARIES ----------
def get_sublord_kp_standard(deg360):
    """
    CORRECTED KP Sublord: Uses exact arc-minute calculations.
    Each nakshatra = 800 arc-minutes, divided by Vimshottari proportions.
    Sublord sequence starts with nakshatra's own lord.
    """
    # Vimshottari sequence
    VIMSHOTTARI_ORDER = ['Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury']
    DASHA_YEARS = [7, 20, 6, 10, 7, 18, 16, 19, 17]  # Total = 120
    
    nak_width = 360.0 / 27.0  # 13°20' = 13.333... degrees
    arc = float(deg360) % 360.0
    nak_idx = int(arc / nak_width)
    if nak_idx >= 27:
        nak_idx = 26
    
    # Get nakshatra lord
    nak_name, nak_lord = NAKSHATRAS[nak_idx]
    
    # Find starting position in Vimshottari cycle
    try:
        start_idx = VIMSHOTTARI_ORDER.index(nak_lord)
    except ValueError:
        start_idx = 0
    
    # Position within nakshatra in ARC-MINUTES (more precise)
    inside_nak_deg = arc - (nak_idx * nak_width)
    inside_nak_minutes = inside_nak_deg * 60.0  # Convert to arc-minutes
    
    # Each nakshatra = 800 arc-minutes
    nak_minutes = 800.0
    
    # Calculate sublord boundaries in arc-minutes
    # Rotate to start with nakshatra's lord
    rotated_lords = VIMSHOTTARI_ORDER[start_idx:] + VIMSHOTTARI_ORDER[:start_idx]
    rotated_years = DASHA_YEARS[start_idx:] + DASHA_YEARS[:start_idx]
    
    total_years = 120.0
    cumulative_minutes = 0.0
    
    for i, years in enumerate(rotated_years):
        # Calculate arc-minutes for this sublord
        sublord_minutes = (years / total_years) * nak_minutes
        cumulative_minutes += sublord_minutes
        
        if inside_nak_minutes <= cumulative_minutes:
            return rotated_lords[i]
    
    return rotated_lords[-1]

# ---------- Helpers ----------
def deg_to_sign_index_and_offset(deg360):
    d = float(deg360) % 360.0
    idx = int(d // 30)
    deg_in = d - idx * 30
    return SIGNS[idx], deg_in

def decdeg_to_dms_string(deg_within_sign):
    """Decimal degrees within sign -> D°M'S\" (seconds precision)."""
    d = int(math.floor(deg_within_sign))
    rem = (deg_within_sign - d) * 60.0
    m = int(math.floor(rem))
    s = int(round((rem - m) * 60.0))
    if s == 60:
        s = 0
        m += 1
    if m == 60:
        m = 0
        d += 1
    return f"{d}°{m:02d}'{s:02d}\""

def _planet_abbr(name: str) -> str:
    mapping = {
        'Sun': 'SUN', 'Moon': 'MOO', 'Mars': 'MAR', 'Mercury': 'MER',
        'Jupiter': 'JUP', 'Venus': 'VEN', 'Saturn': 'SAT',
        'Rahu': 'RAH', 'Ketu': 'KET'
    }
    return mapping.get(name, name[:3].upper())

def get_coordinates(place):
    g = Nominatim(user_agent="astrologyapp")
    loc = g.geocode(place, timeout=10)
    if not loc:
        return None, None
    return loc.latitude, loc.longitude


def _calc_planet_longitude_sidereal(jd_ut, planet_const):
    """Return sidereal longitude using KRISHNAMURTI ayanamsa."""
    try:
        res = swe.calc_ut(jd_ut, planet_const, swe.FLG_SIDEREAL)
        lon = res[0][0] if isinstance(res[0], (list, tuple)) else res[0]
        return float(lon) % 360.0
    except Exception as e:
        print(f"Error calculating {planet_const}: {e}")
        return None




def _calc_planet_longitude_tropical(jd_ut, planet_const):
    """Calculate tropical longitude."""
    try:
        res = swe.calc_ut(jd_ut, planet_const)
        lon = res[0][0] if isinstance(res[0], (list, tuple)) else res[0]
        return float(lon) % 360.0
    except Exception:
        return None

def _calc_ascendant(jd_ut, lat, lng):
    """
    Calculate both tropical and sidereal ascendant/cusps.
    Uses Chitrapaksha ayanamsa (24°01'00") to match reference documents.
    Returns: (asc_sid, cusps_sid, asc_trop, cusps_trop, ayanamsa)
    """
    try:
        # Use FIXED Chitrapaksha ayanamsa instead of swisseph's calculation
        ay = CHITRAPAKSHA_AYANAMSA_DEG  # 24.0166666667°
        
        # Calculate tropical houses using Placidus
        cusps_trop, ascmc_trop = swe.houses(jd_ut, lat, lng, b'P')  # Placidus
        asc_trop = float(ascmc_trop[0]) % 360.0
        cusps_trop = [float(c) % 360.0 for c in cusps_trop[:12]]
        
        # Convert to sidereal using fixed ayanamsa
        asc_sid = (asc_trop - ay) % 360.0
        cusps_sid = [(c - ay) % 360.0 for c in cusps_trop]
        
        return asc_sid, cusps_sid, asc_trop, cusps_trop, ay
    except Exception as e:
        print(f"ERROR in _calc_ascendant: {e}")
        return None, None, None, None, None


import math

def get_nakshatra_and_pada(deg360):
    """
    Return: (nak_name, nak_lord, nak_index, pada)
    Robust to floating rounding and consistent with KP (13°20' nakshatra, 4 padas).
    """
    # normalized degree 0..360
    arc = float(deg360) % 360.0

    # exact nak width in degrees and pada width
    nak_width = 13.0 + (20.0 / 60.0)             # 13°20' = 13.3333333333...
    pada_width = nak_width / 4.0                # 3°20' = 3.3333333333...

    # tiny epsilon to guard against floating point boundaries (~0.5 arc-second)
    eps = 1e-6

    # nakshatra index 0..26
    nak_index = int(math.floor(arc / nak_width))
    if nak_index >= 27:
        nak_index = 26

    nak_name, nak_lord = NAKSHATRAS[nak_index]

    # degree inside the nak (0 <= inside < nak_width)
    inside_nak = arc - (nak_index * nak_width)

    # correct any tiny floating rounding that would make inside_nak == nak_width
    if inside_nak + eps >= nak_width:
        # move to next nakshatra (rare)
        inside_nak = 0.0
        nak_index = min(26, nak_index + 1)
        nak_name, nak_lord = NAKSHATRAS[nak_index]

    # compute pada using floor; add epsilon so boundary cases fall consistently to upper pada
    # e.g. if inside_nak/pada_width is very near to an integer, we want consistent behavior.
    fraction = inside_nak / pada_width
    # If fraction is extremely close to an integer (within eps/pada_width), nudge it a touch
    if abs(round(fraction) - fraction) <= (eps / pada_width):
        fraction = round(fraction)

    pada = int(math.floor(fraction)) + 1

    # clamp pada into 1..4
    if pada < 1:
        pada = 1
    elif pada > 4:
        pada = 4

    return nak_name, nak_lord, nak_index, pada



def classify_position_simple(planet, sign_name, deg_in_sign):
    """Simple Friend/Neutral/Deb classification."""
    own = {
        'Sun':['Leo'], 'Moon':['Cancer'], 'Mars':['Aries','Scorpio'],
        'Mercury':['Gemini','Virgo'], 'Jupiter':['Sagittarius','Pisces'],
        'Venus':['Taurus','Libra'], 'Saturn':['Capricorn','Aquarius']
    }
    if planet in own and sign_name in own[planet]:
        return "Friend"
    
    EXALT = {
        'Sun': ('Aries', 10.0), 'Moon': ('Taurus', 3.0),
        'Mars': ('Capricorn', 28.0), 'Mercury': ('Virgo', 15.0),
        'Jupiter': ('Cancer', 5.0), 'Venus': ('Pisces', 27.0),
        'Saturn': ('Libra', 20.0)
    }
    exalt = EXALT.get(planet)
    if exalt and exalt[0] == sign_name:
        return "Friend"
    
    # Check debilitation (opposite to exaltation)
    DEB = {
        'Sun': 'Libra', 'Moon': 'Scorpio', 'Mars': 'Cancer',
        'Mercury': 'Pisces', 'Jupiter': 'Capricorn',
        'Venus': 'Virgo', 'Saturn': 'Aries'
    }
    if planet in DEB and sign_name == DEB[planet]:
        return "Deb"
    
    return "Neutral"

def calculate_vimshottari_dasha(moon_degree, birth_date):
    """Calculate Vimshottari dasha periods."""
    dasha_lords = ['Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury']
    dasha_years = [7, 20, 6, 10, 7, 18, 16, 19, 17]
    
    nak_width = 13.333333333333334
    nak_num = int((moon_degree % 360.0) / nak_width) % 27
    nak_lord_index = nak_num % 9
    
    inside = (moon_degree % nak_width)
    nak_fraction = inside / nak_width
    
    first_dasha_total = dasha_years[nak_lord_index]
    first_dasha_balance = first_dasha_total * (1.0 - nak_fraction)
    
    dashas = []
    current_start = datetime.combine(birth_date, datetime.min.time())
    
    dashas.append({
        'lord': dasha_lords[nak_lord_index],
        'start': current_start,
        'years': first_dasha_balance,
        'end': current_start + timedelta(days=365.25 * first_dasha_balance)
    })
    
    current_start = dashas[-1]['end']
    for i in range(1, 30):
        li = (nak_lord_index + i) % 9
        years = dasha_years[li]
        dashas.append({
            'lord': dasha_lords[li],
            'start': current_start,
            'years': years,
            'end': current_start + timedelta(days=365.25 * years)
        })
        current_start = dashas[-1]['end']
        if (dashas[-1]['end'] - dashas[0]['start']).days > 365.25 * 210:
            break
    
    return dashas

def get_current_dasha(dashas, current_date):
    """Get current and upcoming dasha."""
    now = current_date if isinstance(current_date, datetime) else datetime.combine(current_date, datetime.min.time())
    for idx, d in enumerate(dashas):
        if d['start'] <= now <= d['end']:
            current = d
            upcoming = dashas[idx + 1] if (idx + 1) < len(dashas) else None
            return current, upcoming
    
    if dashas and now > dashas[-1]['end']:
        return dashas[-1], None
    return None, dashas[0] if dashas else (None, None)

def _compute_jd_from_local_using_place(dob_date, tob_time, place_str):
    """Convert local birth time to Julian Day (UT)."""
    lat, lng = get_coordinates(place_str)
    if lat is None or lng is None:
        return None, None, None, None
    
    local_dt = datetime.combine(dob_date, tob_time)
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lng)
    
    if not tz_name:
        tz_name = "UTC"
        utc_dt = local_dt
    else:
        tz = pytz.timezone(tz_name)
        if local_dt.tzinfo is None:
            local_dt = tz.localize(local_dt)
        utc_dt = local_dt.astimezone(pytz.utc)
    
    year, month, day = utc_dt.year, utc_dt.month, utc_dt.day
    hour_decimal = (utc_dt.hour + utc_dt.minute / 60.0 + 
                   utc_dt.second / 3600.0 + utc_dt.microsecond / 3_600_000_000.0)
    jd_ut = swe.julday(year, month, day, hour_decimal)
    
    return jd_ut, tz_name, lat, lng

def calculate_comprehensive_chart(dob, tob, place):
    """Calculate complete KP chart."""
    lat, lng = get_coordinates(place)
    if lat is None:
        return None, "Could not geocode place."
    
    jd, tz_name, lat, lng = _compute_jd_from_local_using_place(dob, tob, place)
    if jd is None:
        return None, "Could not compute JD / timezone."
    
    # Calculate ascendant and cusps
    asc_sid, cusps_sid, asc_trop, cusps_trop, ay = _calc_ascendant(jd, lat, lng)
    if asc_sid is None:
        return None, "Could not calculate ascendant."
    
    # Calculate planets
    planets = {
        'Sun': swe.SUN, 'Moon': swe.MOON, 'Mars': swe.MARS,
        'Mercury': swe.MERCURY, 'Jupiter': swe.JUPITER,
        'Venus': swe.VENUS, 'Saturn': swe.SATURN, 'Rahu': swe.TRUE_NODE
    }
    
    planet_data = {}
    for name, pid in planets.items():
        lon_sid = _calc_planet_longitude_sidereal(jd, pid)
        if lon_sid is None:
            return None, f"Could not compute {name}"
        
        sign, deg_in = deg_to_sign_index_and_offset(lon_sid)
        deg_dms = decdeg_to_dms_string(deg_in)
        nak_name, nak_lord, nak_index, pada = get_nakshatra_and_pada(lon_sid)
        sublord = get_sublord_kp_standard(lon_sid)
        sign_lord = SIGN_RULERS.get(sign, '')
        position = classify_position_simple(name, sign, deg_in)
        
        planet_data[name] = {
            'full_degree': float(lon_sid),
            'sign': sign,
            'degree': deg_dms,
            'deg_decimal_in_sign': deg_in,
            'nakshatra': nak_name,
            'nakshatra_lord': nak_lord,
            'pada': pada,
            'sublord': sublord,
            'sign_lord': sign_lord,
            'position': position
        }
    
    # Add Ketu (opposite Rahu)
    if 'Rahu' in planet_data:
        rahu_deg = planet_data['Rahu']['full_degree']
        ketu_deg = (rahu_deg + 180.0) % 360.0
        sign, deg_in = deg_to_sign_index_and_offset(ketu_deg)
        deg_dms = decdeg_to_dms_string(deg_in)
        nak_name, nak_lord, nak_index, pada = get_nakshatra_and_pada(ketu_deg)
        
        planet_data['Ketu'] = {
            'full_degree': float(ketu_deg),
            'sign': sign, 'degree': deg_dms, 'deg_decimal_in_sign': deg_in,
            'nakshatra': nak_name, 'nakshatra_lord': nak_lord, 'pada': pada,
            'sublord': get_sublord_kp_standard(ketu_deg),
            'sign_lord': SIGN_RULERS.get(sign,''), 
            'position': classify_position_simple('Ketu', sign, deg_in)
        }
    
    # Calculate house cusps data
    house_data = {}
    house_names = ['1st (Lagna)', '2nd', '3rd', '4th', '5th', '6th',
                   '7th', '8th', '9th', '10th', '11th', '12th']
    
    for i, cusp_deg in enumerate(cusps_sid):
        cusp_deg = float(cusp_deg) % 360.0
        sign, deg_in = deg_to_sign_index_and_offset(cusp_deg)
        deg_dms = decdeg_to_dms_string(deg_in)
        nak_name, nak_lord, nak_index, pada = get_nakshatra_and_pada(cusp_deg)
        sublord = get_sublord_kp_standard(cusp_deg)
        
        house_data[house_names[i]] = {
            'cusp_degree': cusp_deg,
            'sign': sign, 'degree': deg_dms, 'deg_decimal_in_sign': deg_in,
            'nakshatra': nak_name, 'nakshatra_lord': nak_lord, 
            'pada': pada, 'sublord': sublord
        }
    
    # Calculate dashas
    moon_deg = planet_data['Moon']['full_degree']
    dashas = calculate_vimshottari_dasha(moon_deg, datetime.combine(dob, tob))
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
    
    # Get tropical positions for summary
    sun_trop = _calc_planet_longitude_tropical(jd, swe.SUN)
    moon_trop = _calc_planet_longitude_tropical(jd, swe.MOON)
    
    return {
        'houses': house_data,
        'planets': planet_data,
        'dashas': dasha_info,
        'location': {'place': place, 'lat': lat, 'lng': lng, 'tz_name': tz_name},
        'house_cusps_degrees': cusps_sid,
        'asc_degree': asc_sid,
        'ayanamsa': ay,
        'tropical': {'Sun': sun_trop, 'Moon': moon_trop}
    }, None

def get_house_number_from_degree(degree, house_cusps):
    """Determine which house a degree falls into."""
    d = float(degree) % 360
    cusps = [float(c) % 360 for c in house_cusps]
    
    for i in range(12):
        current = cusps[i]
        nxt = cusps[(i + 1) % 12]
        
        if current < nxt:
            if current <= d < nxt:
                return i + 1
        else:  # Wraps around 360
            if d >= current or d < nxt:
                return i + 1
    
    return 1

def render_chart_png_bytes_pil(planet_data, house_cusps_degrees, size=900, show_pada=True):
    """Render East-Indian style chart."""
    pad = int(size * 0.05)
    inner = size - 2 * pad
    cell = inner / 3.0
    ox, oy = pad, pad
    
    bg = (255, 255, 255)
    line_color = (0, 0, 0)
    planet_color = (2, 48, 99)
    house_num_color = (40, 40, 40)
    
    im = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(im)
    
    # Draw outer border
    draw.rectangle([pad // 4, pad // 4, size - pad // 4, size - pad // 4], 
                  outline=line_color, width=max(2, int(size * 0.01)))
    
    # Draw 3x3 grid
    draw.rectangle([ox, oy, ox + inner, oy + inner], 
                  outline=line_color, width=max(1, int(size * 0.003)))
    
    for i in range(1, 3):
        x = ox + i * cell
        y = oy + i * cell
        draw.line([(x, oy), (x, oy + inner)], fill=line_color, width=max(1, int(size * 0.003)))
        draw.line([(ox, y), (ox + inner, y)], fill=line_color, width=max(1, int(size * 0.003)))
    
    # Draw diagonal lines
    x0, x1, x2, x3 = ox, ox + cell, ox + 2 * cell, ox + 3 * cell
    y0, y1, y2, y3 = oy, oy + cell, oy + 2 * cell, oy + 3 * cell
    
    draw.line([(x0, y3), (x1, y2)], fill=line_color, width=max(1, int(size * 0.003)))
    draw.line([(x3, y3), (x2, y2)], fill=line_color, width=max(1, int(size * 0.003)))
    draw.line([(x0, y0), (x1, y1)], fill=line_color, width=max(1, int(size * 0.003)))
    draw.line([(x3, y0), (x2, y1)], fill=line_color, width=max(1, int(size * 0.003)))
    
    # House positions (East-Indian style)
    positions = {
        1:  (ox + 1.50 * cell, oy + 2.68 * cell, 'center'),
        2:  (ox + 2.73 * cell, oy + 2.18 * cell, 'right'),
        3:  (ox + 2.73 * cell, oy + 1.50 * cell, 'right'),
        4:  (ox + 2.73 * cell, oy + 0.32 * cell, 'right'),
        5:  (ox + 1.50 * cell, oy + 0.32 * cell, 'center'),
        6:  (ox + 1.50 * cell, oy + 1.50 * cell, 'center'),
        7:  (ox + 0.27 * cell, oy + 1.50 * cell, 'left'),
        8:  (ox + 0.27 * cell, oy + 2.18 * cell, 'left'),
        9:  (ox + 1.50 * cell, oy + 2.18 * cell, 'center'),
        10: (ox + 0.27 * cell, oy + 0.32 * cell, 'left'),
        11: (ox + 0.27 * cell, oy + 1.82 * cell, 'left'),
        12: (ox + 0.80 * cell, oy + 2.80 * cell, 'center'),
    }
    
    # Group planets by house
    houses = {i: [] for i in range(1, 13)}
    for pname, pdata in planet_data.items():
        full_deg = pdata.get('full_degree') if isinstance(pdata, dict) else pdata
        hnum = get_house_number_from_degree(full_deg, house_cusps_degrees)
        label = _planet_abbr(pname)
        
        if show_pada:
            p = pdata.get('pada')
            if p:
                label = f"{label} p{p}"
        
        houses[hnum].append((pname, label))
    
    # Load fonts
    try:
        house_font_size = max(10, int(size * 0.018))
        planet_font_size = max(11, int(size * 0.030))
        font_house = ImageFont.truetype("DejaVuSans-Bold.ttf", size=house_font_size)
        font_planet = ImageFont.truetype("DejaVuSans-Bold.ttf", size=planet_font_size)
        font_small = ImageFont.truetype("DejaVuSans.ttf", size=max(9, int(size * 0.014)))
    except:
        font_house = ImageFont.load_default()
        font_planet = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Draw house 1 label
    h1_x, h1_y, _ = positions.get(1, (ox + 1.5*cell, oy + 2.68*cell, 'center'))
    label = "1"
    
    try:
        hb = draw.textbbox((0, 0), label, font=font_house)
        hw, hh = hb[2] - hb[0], hb[3] - hb[1]
    except AttributeError:
        hw, hh = draw.textsize(label, font=font_house)
    
    margin = max(6, int(size * 0.01))
    tx = h1_x - hw / 2
    ty = h1_y - hh / 2
    
    draw.rectangle([tx - 4, ty - 2, tx + hw + 4, ty + hh + 2], fill=bg)
    draw.text((tx, ty), label, fill=house_num_color, font=font_house)
    
    # Draw planets
    for h in range(1, 13):
        items = houses[h]
        if not items:
            continue
        
        x, y, anchor = positions.get(h, (ox + 1.5*cell, oy + 1.5*cell, 'center'))
        labels = [lab for (_, lab) in items]
        
        line_heights = []
        for lab in labels:
            try:
                bbox = draw.textbbox((0, 0), lab, font=font_planet)
                lh = bbox[3] - bbox[1]
            except AttributeError:
                _, lh = draw.textsize(lab, font=font_planet)
            line_heights.append(lh)
        
        total_h = sum(line_heights) + (len(line_heights) - 1) * int(size * 0.01)
        start_y = y - (total_h / 2)
        cur_y = start_y
        
        for idx, lab in enumerate(labels):
            try:
                bbox = draw.textbbox((0, 0), lab, font=font_planet)
                w = bbox[2] - bbox[0]
                hgt = bbox[3] - bbox[1]
            except AttributeError:
                w, hgt = draw.textsize(lab, font=font_planet)
            
            if anchor == 'left':
                txp = x
            elif anchor == 'right':
                txp = x - w
            else:
                txp = x - (w / 2.0)
            
            draw.text((txp, cur_y), lab, fill=planet_color, font=font_planet)
            
            try:
                circle_r = max(3, int(size * 0.006))
                draw.ellipse((txp - circle_r*2 - 2, cur_y + hgt/2 - circle_r, 
                            txp - 2, cur_y + hgt/2 + circle_r), fill=planet_color)
            except:
                pass
            
            cur_y += hgt + int(size * 0.01)
    
    # Add footer note
    note = "House 1 shown. Degrees hidden. Generated by AstroGen."
    try:
        nb = draw.textbbox((0, 0), note, font=font_small)
        nw = nb[2] - nb[0]
    except AttributeError:
        nw, _ = draw.textsize(note, font=font_small)
    
    draw.text((size - pad - nw, size - pad + 2), note, fill=(70, 70, 70), font=font_small)
    
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()

# ---------- Numerology helpers ----------
CHALDEAN_MAP = {
    'A':1, 'I':1, 'J':1, 'Q':1, 'Y':1,
    'B':2, 'K':2, 'R':2,
    'C':3, 'G':3, 'L':3, 'S':3,
    'D':4, 'M':4, 'T':4,
    'E':5, 'H':5, 'N':5, 'X':5,
    'U':6, 'V':6, 'W':6,
    'O':7, 'Z':7,
    'F':8, 'P':8
}

def numerology_name_number(name: str) -> int:
    if not name:
        return None
    total = 0
    for ch in name.upper():
        if ch.isalpha():
            total += CHALDEAN_MAP.get(ch, 0)
    
    def reduce_to_digit(n):
        while n > 9:
            n = sum(int(d) for d in str(n))
        return n
    
    return reduce_to_digit(total)

def numerology_life_path(dob):
    parts = dob.strftime("%d%m%Y")
    s = sum(int(ch) for ch in parts)
    while s > 9:
        s = sum(int(d) for d in str(s))
    return s

def generate_pdf_report(birth_data, chart_data, name=None, numerology=None):
    """Generate PDF report."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
                                fontSize=16, textColor=colors.HexColor('#8B4513'),
                                alignment=TA_CENTER, spaceAfter=12)
    
    story.append(Paragraph("🙏 KP ASTROLOGY CHART REPORT", title_style))
    story.append(Spacer(1, 0.1*inch))
    
    # Birth details table
    birth_table_data = [
        ["Name:", name or ""],
        ["Date of Birth:", str(birth_data['dob'])],
        ["Time of Birth:", birth_data.get('tob_display', birth_data['tob'].strftime('%I:%M %p'))],
        ["Place of Birth:", birth_data['place']],
        ["Gender:", birth_data['gender']],
        ["Coordinates:", f"{chart_data['location']['lat']:.3f}°, {chart_data['location']['lng']:.3f}°"],
        ["Ayanamsa:", f"{chart_data.get('ayanamsa', 24.0):.2f}°"]
    ]
    
    if numerology:
        birth_table_data.append(["Name Number:", str(numerology.get('name_number', ''))])
        birth_table_data.append(["Life Path:", str(numerology.get('life_path', ''))])
    
    birth_table = Table(birth_table_data, colWidths=[1.6*inch, 4.4*inch])
    birth_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#FFF8DC')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold')
    ]))
    story.append(birth_table)
    story.append(Spacer(1, 0.15*inch))
    
    # Planetary positions table
    planet_table_data = [["Entity","Sign","Degree","Nakshatra","Pada","Nak Lord","Sub-lord","Sign Lord"]]
    
    # Add Ascendant first
    asc_house = chart_data['houses']['1st (Lagna)']
    planet_table_data.append([
        "Ascendant", 
        asc_house['sign'], 
        asc_house['degree'], 
        asc_house['nakshatra'], 
        str(asc_house.get('pada','')), 
        asc_house['nakshatra_lord'], 
        asc_house['sublord'], 
        SIGN_RULERS.get(asc_house['sign'],'')
    ])
    
    # Group planets by house
    house_map = {i: [] for i in range(1,13)}
    for pname, pdata in chart_data['planets'].items():
        hnum = get_house_number_from_degree(pdata['full_degree'], chart_data['house_cusps_degrees'])
        house_map[hnum].append((pname, pdata))
    
    # Add planets in house order
    for h in range(1, 13):
        for pname, pdata in house_map[h]:
            planet_table_data.append([
                pname,
                pdata['sign'],
                pdata['degree'],
                pdata['nakshatra'],
                str(pdata.get('pada','')),
                pdata['nakshatra_lord'],
                pdata['sublord'],
                pdata.get('sign_lord','')
            ])
    
    planet_table = Table(planet_table_data, colWidths=[0.9*inch, 0.7*inch, 0.9*inch, 1.1*inch, 0.4*inch, 0.9*inch, 0.8*inch, 0.8*inch])
    planet_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8E8E8')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER')
    ]))
    story.append(planet_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Chart image
    png_bytes = render_chart_png_bytes_pil(chart_data['planets'], chart_data['house_cusps_degrees'], size=1200, show_pada=True)
    img_io = io.BytesIO(png_bytes)
    img = RLImage(img_io, width=5*inch, height=5*inch)
    story.append(img)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ========== STREAMLIT UI ==========
st.set_page_config(page_title="🧘‍♂️ AstroGen", page_icon="✨", layout="centered")

# Input form
st.markdown('<div class="card"><h2>Enter your birth details</h2><div class="muted">Provide accurate date, time and place for best results</div></div>', unsafe_allow_html=True)

with st.form("birth_form", clear_on_submit=False):
    left_col, right_col = st.columns([2, 1.15], gap="medium")
    with left_col:
        name_input = st.text_input("Name (optional, for numerology)", value="", placeholder="e.g., Your Name")
        dob_str = st.text_input("Date of Birth (DD/MM/YYYY)", value="", placeholder="e.g., 01/01/1900",
                                help="Enter birth date in DD/MM/YYYY")
        place = st.text_input("Place of Birth", value="", placeholder="Mumbai, India",
                              help="City, Country (for geocoding)")
    with right_col:
        st.write("**Time of Birth**")
        tcols = st.columns([1.1, 1.1, 1.2], gap="small")
        hour_12 = tcols[0].text_input("Hour (1-12)", value="", max_chars=2, placeholder="HH")
        minute = tcols[1].text_input("Minute (0-59)", value="", max_chars=2, placeholder="MM")
        am_pm = tcols[2].radio("Meridian", ["AM", "PM"], horizontal=True, label_visibility="collapsed")
        st.write("")  # spacer
        gender = st.selectbox("Gender", ["Male","Female","Other"], label_visibility="visible")

    submitted = st.form_submit_button("Generate Complete KP Chart ✨")        

if not submitted and "chart_result" not in st.session_state:
    st.info("Enter birth details and press Generate")
    st.stop()
    
# Validate inputs
def _validated_date(s):
    s = s.strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except:
        return None

dob = _validated_date(dob_str)
if dob is None:
    st.error("Enter valid date (DD/MM/YYYY)")
    st.stop()

try:
    h = int(hour_12)
    m = int(minute)
    if not (1 <= h <= 12) or not (0 <= m <= 59):
        raise ValueError()
except:
    st.error("Enter valid time (hour 1-12, minute 0-59)")
    st.stop()

hour_24 = h if (am_pm == "AM" and h != 12) else (0 if (am_pm == "AM" and h == 12) else (h if h == 12 else h + 12))
tob = datetime.strptime(f"{hour_24:02d}:{m:02d}", "%H:%M").time()

# Calculate chart
with st.spinner("Calculating comprehensive KP chart..."):
    chart_result, error = calculate_comprehensive_chart(dob, tob, place)
    if error:
        st.error(error)
        st.stop()
    st.success("✅ Chart computed successfully!")

    st.session_state["chart_result"] = chart_result    

    st.session_state["birth_details"] = {
    'dob': dob,
    'tob': tob,
    'tob_display': f"{hour_12}:{minute} {am_pm}",
    'place': place,
    'gender': gender,
    'name': name_input.strip() if 'name_input' in locals() else ""
    }

    # DEBUG: Show key values for verification
    with st.expander("🔍 Debug Info - Verify Calculations", expanded=False):
        st.write(f"**Ayanamsa:** {chart_result.get('ayanamsa', 'N/A'):.6f}°")
        st.write(f"**Ascendant (sidereal):** {chart_result['asc_degree']:.6f}°")
        
        # Show sublord calculation details for Ascendant
        asc_deg = chart_result['asc_degree']
        nak_width = 360.0 / 27.0
        nak_idx = int(asc_deg / nak_width)
        inside_nak = asc_deg - (nak_idx * nak_width)
        inside_minutes = inside_nak * 60.0
        
        nak_name, nak_lord = NAKSHATRAS[nak_idx]
        st.write(f"**Asc Nakshatra:** {nak_name} (Lord: {nak_lord})")
        st.write(f"**Position in Nak:** {inside_nak:.4f}° = {inside_minutes:.2f} arc-minutes")
        st.write(f"**Calculated Sublord:** {chart_result['houses']['1st (Lagna)']['sublord']}")
        
        st.write("**Planetary Longitudes (sidereal):**")
        for pname in ['Sun', 'Moon', 'Mars', 'Mercury', 'Venus']:
            if pname in chart_result['planets']:
                pdata = chart_result['planets'][pname]
                st.write(f"  - {pname}: {pdata['full_degree']:.6f}° → Sublord: {pdata['sublord']}")

# ========== DISPLAY RESULTS ==========
import html

# Common CSS for both tables
common_css = """
<style>
:root {
  --table-border: #555;
  --table-header-bg: #2c2c2c;
  --table-header-text: #f0f0f0;
  --table-row-even-bg: #1e1e1e;
  --table-row-odd-bg: #292929;
  --table-text-color: #f0f0f0;
  --note-color: #ccc;
}

@media (prefers-color-scheme: light) {
  :root {
    --table-border: #999;
    --table-header-bg: #eae6df;
    --table-header-text: #111;
    --table-row-even-bg: #f9f9f9;
    --table-row-odd-bg: #ffffff;
    --table-text-color: #000;
    --note-color: #555;
  }
}

.summary-table {
  border-collapse: collapse;
  width: 100%;
  max-width: 900px;
  color: var(--table-text-color);
  margin-top: 6px;
}
.summary-table th, .summary-table td {
  padding: 7px 10px;
  border: 1px solid var(--table-border);
  text-align: left;
}
.summary-table th {
  background: var(--table-header-bg);
  color: var(--table-header-text);
  font-weight: 700;
}
.summary-note {
  color: var(--note-color);
  font-size: 12px;
  margin-top: 4px;
}

.kp-table {
  border-collapse: collapse;
  width: 100%;
  max-width: 1100px;
  margin-top: 10px;
  color: var(--table-text-color);
  font-size: 14.5px;
}
.kp-table th, .kp-table td {
  padding: 7px 9px;
  border: 1px solid var(--table-border);
  text-align: center;
}
.kp-table th {
  background: var(--table-header-bg);
  color: var(--table-header-text);
  font-weight: 700;
  text-transform: c talize;
}
.kp-table tbody tr:nth-child(even) {
  background-color: var(--table-row-even-bg);
}
.kp-table tbody tr:nth-child(odd) {
  background-color: var(--table-row-odd-bg);
}
.kp-table tbody tr td:first-child {
  font-weight: 600;
  text-align: left;
  padding-left: 12px;
}
</style>
"""
st.markdown(common_css, unsafe_allow_html=True)

# Summary table
try:
    sun_trop = chart_result.get('tropical', {}).get('Sun')
    moon_trop = chart_result.get('tropical', {}).get('Moon')
    sun_kp = chart_result['planets']['Sun']['full_degree']
    moon_kp = chart_result['planets']['Moon']['full_degree']
    asc_kp = chart_result['asc_degree']
    ayanamsa = chart_result.get('ayanamsa', 24.0)

    if sun_trop is not None:
        st.markdown("### 🌙 Moonshine · Lagna · Sunshine Summary (Tropical & KP)")

        def full_deg_to_sign_dms(full_deg):
            dd = float(full_deg) % 360.0
            sign_index = int(dd // 30)
            deg_in_sign = dd - sign_index * 30
            deg_text = decdeg_to_dms_string(deg_in_sign)
            return SIGNS[sign_index], deg_text

        s_sign, s_txt = full_deg_to_sign_dms(sun_trop)
        m_sign, m_txt = full_deg_to_sign_dms(moon_trop) if moon_trop else ("", "")
        sk_sign, sk_txt = full_deg_to_sign_dms(sun_kp)
        mk_sign, mk_txt = full_deg_to_sign_dms(moon_kp)
        asc_sign, asc_txt = full_deg_to_sign_dms(asc_kp)

        summary_html = f"""
        <table class="summary-table">
          <thead>
            <tr>
              <th>Aspect</th><th>Sign & Degree</th><th>Notes</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>🌞 Tropical Sun</td><td>{html.escape(s_sign + ' ' + s_txt)}</td><td>Western (Tropical) Sun</td></tr>
            <tr><td>🌙 Tropical Moon</td><td>{html.escape(m_sign + ' ' + m_txt)}</td><td>Western (Tropical) Moon</td></tr>
            <tr><td>🌞 KP / Sidereal Sun</td><td>{html.escape(sk_sign + ' ' + sk_txt)}</td><td>KP (Sidereal) Sun</td></tr>
            <tr><td>🌙 KP / Sidereal Moon</td><td>{html.escape(mk_sign + ' ' + mk_txt)}</td><td>KP (Sidereal) Moon</td></tr>
            <tr><td>🏠 Lagna (Ascendant)</td><td>{html.escape(asc_sign + ' ' + asc_txt)}</td><td>KP Ascendant (House 1)</td></tr>
          </tbody>
        </table>
        <div class="summary-note">
          Ayanamsa: {ayanamsa:.2f}° · Timezone: {html.escape(chart_result['location'].get('tz_name','UTC'))} ·
          Lat: {chart_result['location']['lat']:.3f}, Lng: {chart_result['location']['lng']:.3f}
        </div>
        """
        st.markdown(summary_html, unsafe_allow_html=True)
except Exception as e:
    st.error(f"Error building summary: {e}")

# Planetary positions table
try:
    rows = []
    
    # Ascendant first
    asc_house = chart_result['houses']['1st (Lagna)']
    rows.append({
        "Entity": "Asc",
        "Sign": asc_house.get("sign",""),
        "Degree": asc_house.get("degree",""),
        "Position": "",
        "Lord": SIGN_RULERS.get(asc_house.get("sign",""), ""),
        "Nakshatra": asc_house.get("nakshatra",""),
        "Pad": asc_house.get("pada",""),
        "Nakshatra Lord": asc_house.get("nakshatra_lord",""),
        "S. Lord": asc_house.get("sublord","")
    })

    # Group planets by house
    house_map = {i: [] for i in range(1,13)}
    for pname, pdata in chart_result['planets'].items():
        fd = pdata.get('full_degree')
        if fd is None:
            continue
        hnum = get_house_number_from_degree(float(fd), chart_result['house_cusps_degrees'])
        house_map[hnum].append((pname, pdata))

    # Add planets in house order
    for h in range(1, 13):
        for pname, pdata in house_map[h]:
            deg_text = pdata.get('degree', '')
            sign_lord = pdata.get('sign_lord', SIGN_RULERS.get(pdata.get('sign',''), ''))
            rows.append({
                "Entity": pname + (" (R)" if pname in ("Rahu","Ketu") else ""),
                "Sign": pdata.get("sign",""),
                "Degree": deg_text,
                "Position": pdata.get("position",""),
                "Lord": sign_lord,
                "Nakshatra": pdata.get("nakshatra",""),
                "Pad": pdata.get("pada",""),
                "Nakshatra Lord": pdata.get("nakshatra_lord",""),
                "S. Lord": pdata.get("sublord","")
            })

    # Render HTML table
    header_html = """
    <thead>
      <tr>
        <th>Entity</th><th>Sign</th><th>Degree</th><th>Position</th><th>Lord</th>
        <th>Nakshatra</th><th>Pad</th><th>Nakshatra Lord</th><th>S. Lord</th>
      </tr>
    </thead>
    """
    body_html = "<tbody>" + "".join(
        f"<tr>"
        f"<td>{html.escape(str(r.get('Entity','')))}</td>"
        f"<td>{html.escape(str(r.get('Sign','')))}</td>"
        f"<td>{html.escape(str(r.get('Degree','')))}</td>"
        f"<td>{html.escape(str(r.get('Position','')))}</td>"
        f"<td>{html.escape(str(r.get('Lord','')))}</td>"
        f"<td>{html.escape(str(r.get('Nakshatra','')))}</td>"
        f"<td>{html.escape(str(r.get('Pad','')))}</td>"
        f"<td>{html.escape(str(r.get('Nakshatra Lord','')))}</td>"
        f"<td>{html.escape(str(r.get('S. Lord','')))}</td>"
        f"</tr>"
        for r in rows
    ) + "</tbody>"

    table_html = f"<table class='kp-table'>{header_html}{body_html}</table>"

    st.markdown("### 🪐 Planetary Positions (Ordered from Lagna)")
    st.markdown(table_html, unsafe_allow_html=True)
except Exception as e:
    st.error(f"Error building planetary table: {e}")

# Optional house cusps - REMOVED (redundant with planetary table)
# The house cusp information is already shown in the planetary positions table

# Chart image
st.markdown("### 🗺️ East-Indian Lagna Chart")
try:
    png = render_chart_png_bytes_pil(chart_result['planets'], chart_result['house_cusps_degrees'], size=900, show_pada=True)
    st.image(png, width='stretch')
except Exception as e:
    st.error(f"Chart render error: {e}")

# Dasha
st.markdown("### ⏰ Vimshottari Dasha")
d = chart_result['dashas']
if d.get('current'):
    st.markdown(f"**Current:** {d['current']['lord']} — {d['current']['start']} to {d['current']['end']} ({d['current']['years']} years)")
if d.get('upcoming'):
    st.markdown(f"**Upcoming:** {d['upcoming']['lord']} — starts {d['upcoming']['start']} ({d['upcoming']['years']} years)")

# Numerology
name_val = name_input.strip()
numerology = {}
if name_val:
    numerology["name_number"] = numerology_name_number(name_val)
else:
    numerology["name_number"] = None
numerology["life_path"] = numerology_life_path(dob)

if name_val or numerology.get("life_path"):
    st.markdown("### 🔢 Numerology")
    if name_val and numerology.get("name_number"):
        st.write(f"**Name Number ({name_val}):** {numerology['name_number']}")
    st.write(f"**Life Path Number:** {numerology['life_path']}")

# PDF download
pdf_buffer = generate_pdf_report(
    {'dob':dob,'tob':tob,'place':place,'gender':gender,'tob_display':f"{hour_12}:{minute} {am_pm}"}, 
    chart_result, 
    name=name_val, 
    numerology=numerology
)
st.download_button(
    "📥 Download PDF Report", 
    data=pdf_buffer.getvalue(), 
    file_name=f"KP_Chart_{dob}_{uuid.uuid4().hex[:6]}.pdf", 
    mime="application/pdf"
)
# ---------- AI Agent Prompts ----------

# ----------------- AI Agents -----------------
AGENTS = {
    "overall": (
        "You are an expert KP (Krishnamurti Paddhati) astrologer with deep knowledge of Vedic astrology. "
        "Provide a balanced, clear, and actionable overall life reading using KP rules, dasha logic, house-lord "
        "relationships and basic transits where relevant. Be concise, use bullet points for clarity, and avoid "
        "making medical/financial/legal claims."
    ),
    "career": (
        "You are an expert KP astrologer. Focus only on career, vocation, profession, income potential and timing. "
        "Use KP dashas, house-lord relationships for 10th/6th/2nd/11th houses, planets like Jupiter, Saturn, Mercury, "
        "and any career indicators. Suggest practical steps the user can take (skills, timing windows) without giving "
        "financial/legal advice."
    ),
    "relationship": (
        "You are an expert KP astrologer. Focus on relationships, marriage, partnerships and compatibility. Use house-lord "
        "analysis for 7th/5th/8th houses, Venus, Moon, and dasha timing to highlight relationship themes and likely windows. "
        "Give compassionate, practical suggestions and avoid medical/legal claims."
    ),
}

# ----------------- AI-reading function -----------------
def get_ai_reading(agent_type: str) -> str:
    """
    Robust AI-reading function: reads chart + birth details from session_state,
    builds planet/house summaries locally, and calls the LLM.
    Returns a string (or an error message).
    """
    try:
        chart = st.session_state.get("chart_result")
        birth_data = st.session_state.get("birth_details", {})

        if not chart:
            return "⚠️ Chart not available. Please generate the chart first."

        # Build planets_summary safely
        planets_summary_lines = []
        for name, data in chart.get("planets", {}).items():
            sign = data.get("sign", "N/A")
            degree = data.get("degree", f"{data.get('full_degree','N/A')}")
            nak = data.get("nakshatra", "N/A")
            nak_lord = data.get("nakshatra_lord", "N/A")
            sublord = data.get("sublord", "N/A")
            planets_summary_lines.append(
                f"- {name}: {sign} ({degree}) | Nakshatra: {nak} (Lord: {nak_lord}) | Sub-lord: {sublord}"
            )
        planets_summary = "\n".join(planets_summary_lines) if planets_summary_lines else "No planetary data."

        # Build houses_summary safely
        houses_summary_lines = []
        for hname, hdata in chart.get("houses", {}).items():
            sign = hdata.get("sign", "N/A")
            nak = hdata.get("nakshatra", "N/A")
            sublord = hdata.get("sublord", "N/A")
            houses_summary_lines.append(f"- {hname}: {sign} | Nakshatra: {nak} | Sub-lord: {sublord}")
        houses_summary = "\n".join(houses_summary_lines) if houses_summary_lines else "No house data."

        display_time = birth_data.get("tob_display", "N/A")
        chart_dashas = chart.get("dashas", {})
        current_dasha = chart_dashas.get("current", {})
        upcoming_dasha = chart_dashas.get("upcoming", {})

        chart_summary = f"""
Birth Details:
Date: {birth_data.get('dob', 'N/A')}
Time: {display_time}
Place: {birth_data.get('place', 'N/A')}
Gender: {birth_data.get('gender', 'N/A')}

=== PLANETARY POSITIONS (KP) ===
{planets_summary}

=== HOUSE CUSPS (KP) ===
{houses_summary}

=== VIMSHOTTARI DASHA ===
Current Dasha: {current_dasha.get('lord', 'N/A')}
Period: {current_dasha.get('start', 'N/A')} to {current_dasha.get('end', 'N/A')}
Upcoming Dasha: {upcoming_dasha.get('lord', 'N/A')} (starts {upcoming_dasha.get('start', 'N/A')})

Please provide a detailed KP analysis using the above data.
"""

        with st.spinner("🔮 Analyzing your complete chart..."):
            system_prompt = AGENTS.get(agent_type, AGENTS.get("overall"))
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # safe, compact model used elsewhere; change if you prefer another
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": chart_summary},
                ],
                max_tokens=1200,
                temperature=0.7,
            )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Error in get_ai_reading: {str(e)}"

# ----------------- AI Readings UI -----------------
st.markdown("---")
st.markdown("### 🔮 AI Astrological Readings")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🌟 Overall Life"):
        st.session_state["overall_result"] = get_ai_reading("overall")
with col2:
    if st.button("💼 Career"):
        st.session_state["career_result"] = get_ai_reading("career")
with col3:
    if st.button("💖 Relationship"):
        st.session_state["relationship_result"] = get_ai_reading("relationship")

if "overall_result" in st.session_state:
    st.markdown("#### 🌟 Overall Life Reading")
    st.markdown(st.session_state["overall_result"])

if "career_result" in st.session_state:
    st.markdown("#### 💼 Career Reading")
    st.markdown(st.session_state["career_result"])

if "relationship_result" in st.session_state:
    st.markdown("#### 💖 Relationship Reading")
    st.markdown(st.session_state["relationship_result"])

# ----------------- Chat -----------------
st.markdown("---")
st.markdown("### 💬 Ask Yogi Baba")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "🧘‍♂️ Hello! I am ready 😊 I have now seen all your stars — ask me anything about your destiny."}
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input handling
if prompt := st.chat_input("Ask Yogi Baba about your chart..."):
    # Save the user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    chart = st.session_state.get("chart_result")
    birth_data = st.session_state.get("birth_details", {})

    # If chart or birth details are missing, show a friendly assistant message and skip API call
    if not chart or not birth_data:
        assistant_msg = "⚠️ Please generate your KP chart first (fill birth details and press Generate)."
        with st.chat_message("assistant"):
            st.markdown(assistant_msg)
        st.session_state.messages.append({"role": "assistant", "content": assistant_msg})
    else:
        # Build safe summaries for the chat context
        house_summary_lines = []
        for name, data in chart.get("houses", {}).items():
            house_summary_lines.append(f"- {name}: {data.get('sign','N/A')} | Sub-lord: {data.get('sublord','N/A')}")
        house_summary = "\n".join(house_summary_lines) if house_summary_lines else "No house data."

        planet_summary_lines = []
        for name, data in chart.get("planets", {}).items():
            planet_summary_lines.append(f"- {name}: {data.get('sign','N/A')} ({data.get('nakshatra','N/A')}) | Sub-lord: {data.get('sublord','N/A')}")
        planet_summary = "\n".join(planet_summary_lines) if planet_summary_lines else "No planetary data."

        dasha = chart.get("dashas", {})
        current_dasha = dasha.get("current", {}).get("lord", "Not available")
        upcoming_dasha = dasha.get("upcoming", {}).get("lord", "Not available")

        context = f"""
📅 Current Date: {datetime.now().strftime("%B %d, %Y")}

🌙 Birth Details:
Date of Birth: {birth_data.get('dob', 'N/A')}
Time of Birth: {birth_data.get('tob_display', 'N/A')}
Place of Birth: {birth_data.get('place', 'N/A')}
Gender: {birth_data.get('gender', 'N/A')}

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
