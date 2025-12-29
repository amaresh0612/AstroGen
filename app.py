# app.py (FIXED VERSION - Aligned with reference calculations)
import streamlit as st
from openai import OpenAI
import os, uuid, io
from datetime import datetime, timedelta
import swisseph as swe
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz
import math
import html
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
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


KP_MODE = "modern"   # options: "modern" | "legacy"

# --- Global sidereal mode (Lahiri / Chitrapaksha) ---
swe.set_sid_mode(swe.SIDM_LAHIRI)
#CHITRAPAKSHA_AYANAMSA_DEG = 24.0002777778
#try:
    # Preferred: set a USER sidereal mode with the fixed Chitrapaksha value
   # swe.set_sid_mode(swe.SIDM_USER, CHITRAPAKSHA_AYANAMSA_DEG)
#except Exception:
    # Fallback to KRISHNAMURTI if USER not supported
   # try:
     #   swe.set_sid_mode(swe.SIDM_KRISHNAMURTI)
    #except Exception:
        # Last-resort: leave default but warn
       # print("Warning: unable to set user/krishnamurti sidereal mode; results may vary.")
# ---------- Config ----------
#CHITRAPAKSHA_AYANAMSA_DEG = 24.0166666667 # 24°01'00" - Chitrapaksha standard

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
    # LOCAL LOOKUP: Precise coordinates for requested cities
    fallback_places = {
        "Bhubaneswar": (20.2961, 85.8245),
        "Bhubaneshwar": (20.2961, 85.8245),
        "Bhubaneswar, Odisha": (20.2961, 85.8245),
        "Cuttack": (20.4625, 85.8830),
        "Cuttack, Odisha": (20.4625, 85.8830),
        "Jamshedpur": (22.8046, 86.2029),
        "Jamshedpur, Jharkhand": (22.8046, 86.2029),
        "Brajrajnagar": (21.8211, 83.9189),
        "Brajrajnagar, Odisha": (21.8211, 83.9189),
        "Delhi": (28.6139, 77.2090),
        "Mumbai": (19.0760, 72.8777),
        "Kolkata": (22.5726, 88.3639)
    }

    # 1. Clean the input
    user_input = place.strip()
    
    # 2. Check for exact match
    if user_input in fallback_places:
        return fallback_places[user_input]
    
    # 3. Check for partial match (if user types "Cuttack India", it finds "Cuttack")
    for city_name, coords in fallback_places.items():
        if city_name.lower() in user_input.lower():
            return coords

    # 4. Try external Geocoding if not in local list
    try:
        g = Nominatim(user_agent="astrogen-app")
        loc = g.geocode(user_input, timeout=10)
        if loc:
            return loc.latitude, loc.longitude
    except:
        pass

    # 5. Final Guard: If all else fails, return None to trigger an error 
    # rather than calculating for the wrong city.
    return None



def _calc_planet_longitude_sidereal(jd_ut, planet_const):
    try:
        # 1. Set the correct Sidereal Mode (Lahiri/Chitrapaksha)
        #swe.set_sid_mode(swe.SIDM_LAHIRI) 
        
        # 2. Get the specific Ayanamsa for THIS Julian Day
        ayanamsa_val = swe.get_ayanamsa_ut(jd_ut)
        
        # 3. Calculate tropical longitude
        res = swe.calc_ut(jd_ut, planet_const, swe.FLG_SWIEPH)
        lon_trop = res[0][0]
        
        # 4. Subtract the DYNAMIC ayanamsa
        #lon_sid = (lon_trop - ayanamsa_val) % 360.0
        lon_sid = kp_round((lon_trop - ayanamsa_val) % 360.0)
        return lon_sid
    except Exception as e:
        print(f"Error: {e}")
        return None


def _calc_planet_longitude_tropical(jd_ut, planet_const):
    """Tropical longitude using SWIEPH."""
    try:
        res = swe.calc_ut(jd_ut, planet_const, swe.FLG_SWIEPH)
        lon = res[0][0] if isinstance(res[0], (list, tuple)) else res[0]
        return float(lon) % 360.0
    except Exception as e:
        print("Tropical calc error:", e)
        return None

def _calc_ascendant(jd_ut, lat, lng):
    # Set to Lahiri to match standard 1964 charts
    #swe.set_sid_mode(swe.SIDM_LAHIRI)
    ay = swe.get_ayanamsa_ut(jd_ut)
    
    cusps_trop, ascmc_trop = swe.houses(jd_ut, lat, lng, b'P')
    #asc_sid = (ascmc_trop[0] - ay) % 360.0
    asc_sid = kp_round((ascmc_trop[0] - ay) % 360.0)
    #cusps_sid = [(c - ay) % 360.0 for c in cusps_trop]
    cusps_sid = [kp_round((c - ay) % 360.0) for c in cusps_trop]
    return asc_sid, cusps_sid, ascmc_trop[0], cusps_trop, ay


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


def compute_pratyantardashas(bhukti_dasha, all_dasha_years=[7,20,6,10,7,18,16,19,17], 
                             all_dasha_lords=['Ketu','Venus','Sun','Moon','Mars','Rahu','Jupiter','Saturn','Mercury']):
    """
    Divides a Bhukti (level 2) into 9 Pratyantardashas (level 3).
    Formula: (Bhukti Years * Planet Years) / 120
    """
    bhukti_years = float(bhukti_dasha['years'])
    denom = 120.0
    pratyantars = []
    cur = bhukti_dasha['start']
    
    # Sequence starts from the Bhukti lord
    try:
        start_idx = all_dasha_lords.index(bhukti_dasha['lord'])
    except:
        start_idx = 0

    for i in range(9):
        idx = (start_idx + i) % 9
        p_years = bhukti_years * (all_dasha_years[idx] / denom)
        end_dt = cur + timedelta(days=365.25 * p_years)
        pratyantars.append({
            'lord': all_dasha_lords[idx],
            'start': cur,
            'end': end_dt,
            'years': p_years
        })
        cur = end_dt
    
    if pratyantars:
        pratyantars[-1]['end'] = bhukti_dasha['end']
    return pratyantars

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


def calculate_vimshottari_dasha(moon_degree: float, birth_dt: datetime):
    """
    Calculate Vimshottari mahadashas starting at birth_dt.
    - moon_degree: sidereal Moon longitude in degrees (0..360).
    - birth_dt: a datetime (preferably aware or local as used elsewhere).
    Returns: list of mahadashas in order (each dict has lord, start, end, years).
    """
    # Standard Vimshottari order & durations (years)
    dasha_lords = ['Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury']
    dasha_years = [7, 20, 6, 10, 7, 18, 16, 19, 17]
    total_cycle_years = sum(dasha_years)  # should be 120

    # Compute which nakshatra (0..26) the moon is in and fraction inside it
    nak_width = 360.0 / 27.0  # 13°20'
    moon_arc = float(moon_degree) % 360.0
    nak_idx = int(math.floor(moon_arc / nak_width))
    if nak_idx >= 27:
        nak_idx = 26

    # get nakshatra lord from your NAKSHATRAS lookup
    nak_name, nak_lord = NAKSHATRAS[nak_idx]

    # fraction inside the nakshatra (0..1)
    inside_deg = moon_arc - (nak_idx * nak_width)
    nak_fraction = inside_deg / nak_width

    # the starting mahadasha is the one ruled by the nakshatra lord
    try:
        start_idx = dasha_lords.index(nak_lord)
    except ValueError:
        # fallback to Moon index (safe default)
        start_idx = dasha_lords.index('Moon')

    # remaining portion of the first mahadasha (in years)
    first_maha_total = dasha_years[start_idx]
    first_maha_balance = first_maha_total * (1.0 - nak_fraction)

    dashas = []
    current_start = birth_dt if isinstance(birth_dt, datetime) else datetime.combine(birth_dt, datetime.min.time())

    # First (balance) mahadasha
    first_end = current_start + timedelta(days=365.25 * first_maha_balance)
    dashas.append({
        'lord': dasha_lords[start_idx],
        'start': current_start,
        'years': first_maha_balance,
        'end': first_end
    })

    # subsequent full mahadashas until a safe horizon (e.g., 210 years) or count cap
    # subsequent full mahadashas until a safe horizon (100 years) or count cap
    current_start = first_end
    i = 1
    while True:
        idx = (start_idx + i) % 9
        years = dasha_years[idx]
        end_dt = current_start + timedelta(days=365.25 * years)
        dashas.append({
            'lord': dasha_lords[idx],
            'start': current_start,
            'years': years,
            'end': end_dt
        })
        current_start = end_dt
        i += 1
        # STOP when mahadasha end would exceed 100 years from the first mahadasha start
        horizon_days = 365.25 * 100.0
        if (dashas[-1]['end'] - dashas[0]['start']).days > horizon_days:
            # trim the last if it overshot the 100-year horizon
            if (dashas[-1]['start'] - dashas[0]['start']).days >= horizon_days:
                dashas.pop()  # remove last completely if it starts beyond horizon
            else:
                # clamp the end date to the horizon boundary
                dashas[-1]['end'] = dashas[0]['start'] + timedelta(days=horizon_days)
                dashas[-1]['years'] = (dashas[-1]['end'] - dashas[-1]['start']).days / 365.25
            break
        if i > 40:  # defensive cap
            break


    return dashas


def compute_antardashas(maha_dasha, all_dasha_years = [7,20,6,10,7,18,16,19,17],
                        all_dasha_lords = ['Ketu','Venus','Sun','Moon','Mars','Rahu','Jupiter','Saturn','Mercury']):
    """
    Given one maha_dasha dict with 'lord','start','years','end', return a list of 9 antardashas.
    Each antar-dasha has proportional length = maha_length * (planet_year / 120).
    Returns list of dicts {lord, start, end, years}
    """
    maha_years = float(maha_dasha['years'])
    # normalization denominator = 120 (sum of Vimshottari years)
    denom = float(sum(all_dasha_years))
    antars = []
    cur = maha_dasha['start']
    # Find cycle index where first antar starts — antar cycle always begins with same planet order as Vimshottari,
    # but the antar cycle for a given maha starts from its own starting point: the antar sequence for a maha
    # begins from the maha's starting lord index in the Vimshottari cycle.
    try:
        start_idx = all_dasha_lords.index(maha_dasha['lord'])
    except ValueError:
        start_idx = 0

    for i in range(9):
        idx = (start_idx + i) % 9
        antar_years = maha_years * (all_dasha_years[idx] / denom)
        end_dt = cur + timedelta(days=365.25 * antar_years)
        antars.append({
            'lord': all_dasha_lords[idx],
            'start': cur,
            'years': antar_years,
            'end': end_dt
        })
        cur = end_dt

    # Guard: ensure last antar end aligns with maha end (adjust tiny float drift)
    if antars:
        antars[-1]['end'] = maha_dasha['end']
    return antars


def kp_round(deg):
    """
    KP rounding:
    - modern  → no rounding
    - legacy  → round to nearest arc-minute
    """
    if KP_MODE == "legacy":
        return round(deg * 60.0) / 60.0
    return deg


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


# ------------------- NEW / FIXED FUNCTIONS -------------------

def get_all_cuspal_sublords(house_cusps, get_sublord_fn):
    """
    Compute full 12 cuspal sub-lords from the _cusp degrees_ list.
    - house_cusps: iterable of 12 degrees (0..360)
    - get_sublord_fn: function(deg360) -> sublord name (your get_sublord_kp_standard)

    Returns dict keyed by '1'..'12' with sublord string values.
    """
    mapping = {}
    for i, cusp_deg in enumerate(house_cusps, start=1):
        try:
            deg = float(cusp_deg) % 360.0
            sublord = get_sublord_fn(deg)
        except Exception:
            sublord = ""
        mapping[str(i)] = sublord
    return mapping


def get_house_number_whole_sign(degree, asc_degree):
    """
    Determine house number using WHOLE-SIGN system:
      - Identify sign index (0..11) of the given degree
      - Identify ascendant's sign index
      - House number = ((planet_sign_index - asc_sign_index) mod 12) + 1

    Returns integer 1..12.
    """
    d = float(degree) % 360.0
    asc = float(asc_degree) % 360.0
    sign_idx = int(d // 30)  # 0..11
    asc_sign_idx = int(asc // 30)
    house = ((sign_idx - asc_sign_idx) % 12) + 1
    return house



def _compute_jd_from_local_using_place(dob_date, tob_time, place_str):
    """
    Convert local birth time to Julian Day (UT).
    CRITICAL FIX: Add 10.5-second correction to match reference software.
    """
    lat, lng = get_coordinates(place_str)
    if lat is None or lng is None:
        return None, None, None, None
    
    # CORRECTION: Add 10.5 seconds to match reference IMAGE
    # Reference software appears to round/calculate time slightly differently
    #from datetime import timedelta
    #corrected_tob = (datetime.combine(dob_date, tob_time) + timedelta(seconds=10.5)).time()
    
    #local_dt = datetime.combine(dob_date, corrected_tob)
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
        # ---------- compute cuspal sublords once ----------
        cuspal_map = get_all_cuspal_sublords(cusps_sid, get_sublord_kp_standard)

        for pname, pdata in planet_data.items():
            fd = float(pdata.get('full_degree', 0.0)) % 360.0
            pdata['house_cuspal'] = get_house_number_from_degree(fd, cusps_sid)
            pdata['house_whole'] = get_house_number_whole_sign(fd, asc_sid)

        # Ascendant whole-sign (should always be 1)
        asc_whole = get_house_number_whole_sign(asc_sid, asc_sid)
    # Calculate dashas
    moon_deg = planet_data['Moon']['full_degree']
    # compute full raw list (list of mahadasha dicts)
    raw_dashas = calculate_vimshottari_dasha(moon_deg, datetime.combine(dob, tob))

    # find current & upcoming using helper
    current_dasha, upcoming_dasha = get_current_dasha(raw_dashas, datetime.now())

    
    dasha_info = {
        'raw': raw_dashas,   # <-- important: full list used by PDF table
        'current': {
            'lord': current_dasha['lord'],
            'start': current_dasha['start'].strftime('%Y-%m-%d'),
            'end': current_dasha['end'].strftime('%Y-%m-%d'),
            'years': f"{current_dasha['years']:.2f}"
        } if current_dasha else None,
        'upcoming': {
            'lord': upcoming_dasha['lord'],
            'start': upcoming_dasha['start'].strftime('%Y-%m-%d'),
            'years': f"{upcoming_dasha['years']:.2f}"
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
        'asc_whole': asc_whole,
        'cuspal_sublords': cuspal_map,
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

        if isinstance(pdata, dict):
            hnum = pdata.get('house_whole') or get_house_number_from_degree(full_deg, house_cusps_degrees)
        else:
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
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.45*inch, rightMargin=0.45*inch, topMargin=0.5*inch, bottomMargin=0.5*inch)
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

    # === ADD FULL 12 CSLs TO PDF ===
    csl_all = chart_data.get("cuspal_sublords", {}) or st.session_state.get("cuspal_sublords", {})

    
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

    # --- Insert near top of generate_pdf_report, after styles defined ---
    wrap_style = ParagraphStyle(
        'Wrap',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=8,
        alignment=TA_LEFT,
        wordWrap='LTR',
    )

    # Planetary positions table
    # Planetary positions table (wrapped Paragraph cells, 10 columns)
    planet_table_data = [
        [
            "House","Entity","Sign","Degree","Nakshatra",
            "Pada","Nak Lord","Sub-lord","Sign Lord","Cusp Sublord"
        ]
    ]

    # Reuse wrap_style (already defined above)
    def P(text):
        text = "" if text is None else str(text)
        return Paragraph(html.escape(text), wrap_style)

    # Ascendant row (use Paragraphs to allow wrapping)
    asc_house = chart_data['houses']['1st (Lagna)']
    csl_all_pdf = chart_data.get('cuspal_sublords', {}) or (st.session_state.get("cuspal_sublords", {}))
    planet_table_data.append([
        P("1 (Lagna)"),
        P("Ascendant"),
        P(asc_house.get('sign','')),
        P(asc_house.get('degree','')),
        P(asc_house.get('nakshatra','')),
        P(str(asc_house.get('pada',''))),
        P(asc_house.get('nakshatra_lord','')),
        P(asc_house.get('sublord','')),
        P(SIGN_RULERS.get(asc_house.get('sign',''), '')),
        P(csl_all_pdf.get("1",""))
    ])

    # Group planets by whole-sign house (fall back to cuspal)
    house_map = {i: [] for i in range(1,13)}
    for pname, pdata in chart_data['planets'].items():
        hnum = pdata.get('house_whole') or pdata.get('house_cuspal') or get_house_number_whole_sign(pdata['full_degree'], chart_data['asc_degree'])
        house_map[int(hnum)].append((pname, pdata))

    # Add planet rows (use Paragraph for each cell)
    for h in range(1, 13):
        for pname, pdata in house_map[h]:
            planet_table_data.append([
                P(str(h)),
                P(pname + (" (R)" if pname in ("Rahu","Ketu") else "")),
                P(pdata.get('sign','')),
                P(pdata.get('degree','')),
                P(pdata.get('nakshatra','')),
                P(str(pdata.get('pada',''))),
                P(pdata.get('nakshatra_lord','')),
                P(pdata.get('sublord','')),
                P(pdata.get('sign_lord','')),
                P(csl_all_pdf.get(str(h), ""))
            ])

    # Ten column widths that fit your A4 printable area with the margins used above
    col_widths = [
        0.45*inch,  # House
        1.00*inch,  # Entity
        0.7*inch,   # Sign
        0.8*inch,   # Degree
        1.6*inch,   # Nakshatra
        0.35*inch,  # Pada
        0.8*inch,   # Nak Lord
        0.8*inch,   # Sub-lord
        0.8*inch,   # Sign Lord
        1.0*inch    # Cusp Sublord
    ]

    planet_table = Table(planet_table_data, colWidths=col_widths, repeatRows=1)
    planet_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8E8E8')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('GRID', (0,0), (-1,-1), 0.35, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(planet_table)
    story.append(Spacer(1, 0.15*inch))

    # Chart image
    png_bytes = render_chart_png_bytes_pil(chart_data['planets'], chart_data['house_cusps_degrees'], size=1200, show_pada=True)
    img_io = io.BytesIO(png_bytes)
    img = RLImage(img_io, width=4.5*inch, height=4.5*inch) 
    story.append(img)

    # --- Vimshottari Dasha + Antardasha table with durations (years) ---
    from datetime import datetime as _dt

    # load raw dashas from chart_data / session
    raw_dashas = None
    if isinstance(chart_data.get('dashas'), dict) and chart_data['dashas'].get('raw'):
        raw_dashas = list(chart_data['dashas']['raw'])
    elif st.session_state.get("chart_result", {}).get('raw_dashas'):
        raw_dashas = list(st.session_state["chart_result"]['raw_dashas'])

    # normalize: ensure dates are datetimes
    def _ensure_dt(x):
        if isinstance(x, _dt):
            return x
        try:
            return _dt.fromisoformat(str(x))
        except Exception:
            try:
                return _dt.strptime(str(x), "%Y-%m-%d")
            except Exception:
                return None

    if raw_dashas:
        # ensure each item has datetime objects
        for r in raw_dashas:
            if not isinstance(r.get('start'), _dt):
                r['start'] = _ensure_dt(r.get('start')) or r.get('start')
            if not isinstance(r.get('end'), _dt):
                r['end'] = _ensure_dt(r.get('end')) or r.get('end')

        # apply 100-year horizon relative to first mahadasha start
        first_start = raw_dashas[0].get('start')
        if isinstance(first_start, _dt):
            horizon_end = first_start + timedelta(days=365.25 * 100.0)
            filtered = []
            for r in raw_dashas:
                r_start = r.get('start')
                if not isinstance(r_start, _dt):
                    continue
                if r_start <= horizon_end:
                    # if r['end'] extends past horizon, clamp it
                    if isinstance(r.get('end'), _dt) and r['end'] > horizon_end:
                        r = r.copy()
                        r['end'] = horizon_end
                        r['years'] = (r['end'] - r['start']).days / 365.25
                    filtered.append(r)
            raw_dashas = filtered
        else:
            # if first_start is not a datetime, fall back to trimming the first ~12 dasha items
            raw_dashas = raw_dashas[:12]

    # --- FINAL ADJUSTMENT: Match Reference Image Structure and Values ---
    if raw_dashas:
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Vimshottari Dasha: Mahadasha > Antardasha > Pratyantardasha", styles['Heading3']))
        
        # Flattened table to match image columns: DASA, BHUKTI, ANTARDASA, DATE, MONTH, YEAR
        # Note: Your naming request (Antardasha/Pratyantardasha) is mapped to image's BHUKTI/ANTARDASA
        dash_table_data = [["DASA", "ANTARDASHA", "PRATYANTARDASHA", "DATE", "MONTH", "YEAR"]]

        for maha in raw_dashas:
            # Filter for the relevant window seen in image (2024-2030)
            if maha['end'].year < 2024: continue
            if maha['start'].year > 2032: break
            
            antars = compute_antardashas(maha)
            for antar in antars:
                pratyantars = compute_pratyantardashas(antar)
                for p in pratyantars:
                    # One row per change to match the image format
                    dash_table_data.append([
                        maha['lord'].upper(),
                        antar['lord'].upper(), # Level 2
                        p['lord'].upper(),     # Level 3
                        p['start'].strftime('%d'),
                        p['start'].strftime('%m'),
                        p['start'].strftime('%Y')
                    ])

        # Widths adjusted for the 6-column "Uncle's Report" style
        dt = Table(dash_table_data, colWidths=[1.1*inch, 1.2*inch, 1.5*inch, 0.6*inch, 0.7*inch, 0.8*inch], repeatRows=1)
        dt.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#EDECEC')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ALIGN', (3,0), (-1,-1), 'CENTER'), # Center Date/Month/Year
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(dt)


        story.append(Spacer(1, 0.1*inch))



    doc.build(story)
    buffer.seek(0)
    return buffer

# ========== STREAMLIT UI ==========
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
    # === store all 12 cuspal sub-lords ===
    csl_map = chart_result.get('cuspal_sublords') \
              or get_all_cuspal_sublords(chart_result['house_cusps_degrees'], get_sublord_kp_standard)
    st.session_state["chart_result"]['cuspal_sublords'] = csl_map
    st.session_state["cuspal_sublords"] = csl_map
    # === END ADD ===


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
# Planetary positions table
try:
    # Ensure cuspal sub-lords map is available in this scope
    csl_all = chart_result.get('cuspal_sublords', {}) or st.session_state.get('cuspal_sublords', {})

    rows = []
    
    # Ascendant first - ensure house number variable exists
    asc_house = chart_result['houses']['1st (Lagna)']
    hnum = 1  # Ascendant is house 1
    rows.append({
        "House": hnum,
        "Entity": "Asc",
        "Sign": asc_house.get("sign",""),
        "Degree": asc_house.get("degree",""),
        "Position": "",
        "Lord": SIGN_RULERS.get(asc_house.get("sign",""), ""),
        "Nakshatra": asc_house.get("nakshatra",""),
        "Pad": asc_house.get("pada",""),
        "Nakshatra Lord": asc_house.get("nakshatra_lord",""),
        "S. Lord": asc_house.get("sublord",""),
        "Cusp Sublord": csl_all.get("1","") 
    })

    # Group planets by house
    house_map = {i: [] for i in range(1,13)}
    for pname, pdata in chart_result['planets'].items():
        fd = pdata.get('full_degree')
        if fd is None:
            continue
        hnum = pdata.get('house_whole') or pdata.get('house_cuspal') or get_house_number_whole_sign(float(fd), chart_result['asc_degree'])
        house_map[int(hnum)].append((pname, pdata))
    # Add planets in house order
    for h in range(1, 13):
        for pname, pdata in house_map[h]:
            deg_text = pdata.get('degree', '')
            sign_lord = pdata.get('sign_lord', SIGN_RULERS.get(pdata.get('sign',''), ''))
            rows.append({
                "House": h,
                "Entity": pname + (" (R)" if pname in ("Rahu","Ketu") else ""),
                "Sign": pdata.get("sign",""),
                "Degree": deg_text,
                "Position": pdata.get("position",""),
                "Lord": sign_lord,
                "Nakshatra": pdata.get("nakshatra",""),
                "Pad": pdata.get("pada",""),
                "Nakshatra Lord": pdata.get("nakshatra_lord",""),
                "S. Lord": pdata.get("sublord",""),
                "Cusp Sublord": csl_all.get(str(h), "") 
            })

    # Render HTML table
    header_html = """
    <thead>
      <tr>
        <th>House</th><th>Entity</th><th>Sign</th><th>Degree</th><th>Position</th><th>Lord</th>
        <th>Nakshatra</th><th>Pad</th><th>Nakshatra Lord</th><th>S. Lord</th><th>Cusp Sublord</th>
      </tr>
    </thead>
    """
    body_html = "<tbody>" + "".join(
        f"<tr>"
        f"<td>{html.escape(str(r.get('House','')))}</td>"
        f"<td>{html.escape(str(r.get('Entity','')))}</td>"
        f"<td>{html.escape(str(r.get('Sign','')))}</td>"
        f"<td>{html.escape(str(r.get('Degree','')))}</td>"
        f"<td>{html.escape(str(r.get('Position','')))}</td>"
        f"<td>{html.escape(str(r.get('Lord','')))}</td>"
        f"<td>{html.escape(str(r.get('Nakshatra','')))}</td>"
        f"<td>{html.escape(str(r.get('Pad','')))}</td>"
        f"<td>{html.escape(str(r.get('Nakshatra Lord','')))}</td>"
        f"<td>{html.escape(str(r.get('S. Lord','')))}</td>"
        f"<td>{html.escape(str(r.get('Cusp Sublord','')))}</td>"
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
