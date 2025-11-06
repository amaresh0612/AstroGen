# app.py (updated) -- uses Pillow fallback for chart rendering (no pycairo/renderPM)
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

# keep the reportlab graphics imports (vector drawing) if you want to keep the vector drawing function
from reportlab.graphics.shapes import Drawing, Rect, Line, String

# Pillow imports (used for robust PNG rendering)
from PIL import Image, ImageDraw, ImageFont

# ---------- Setup ----------
st.set_page_config(page_title="🧘‍♂️ AstroGen", page_icon="✨", layout="centered")

# ---------- Theme-aware CSS (replace existing CSS blocks & header) ----------

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
    """
    Determine house number (1..12) for a planet at `degree` (0..360),
    given `house_cusps` list of 12 cusp degrees.
    """
    d = degree % 360
    cusps = [c % 360 for c in house_cusps]
    for i in range(12):
        current = cusps[i]
        nxt = cusps[(i + 1) % 12]
        if current < nxt:
            if current <= d < nxt:
                return i + 1
        else:
            # wrap case
            if d >= current or d < nxt:
                return i + 1
    return 1

def _planet_abbr(name: str) -> str:
    mapping = {
        'Sun': 'SUN', 'Moon': 'MOO', 'Mars': 'MAR', 'Mercury': 'MER',
        'Jupiter': 'JUP', 'Venus': 'VEN', 'Saturn': 'SAT',
        'Rahu': 'RAH', 'Ketu': 'KET'
    }
    return mapping.get(name, name[:3].upper())

# -----------------------------
# Sample data (adjust as needed)
# -----------------------------
# sample house cusps in degrees (12 values). You can replace with your real cusps.
sample_house_cusps = [
    15.0, 45.0, 75.0, 105.0, 135.0, 165.0,
    195.0, 225.0, 255.0, 285.0, 315.0, 345.0
]

# sample planet positions (full_degree 0..360)
sample_planets = {
    "Sun": 14.2,     # near house 1 cusp example
    "Moon": 182.5,
    "Mars": 300.0,
    "Mercury": 46.3,
    "Jupiter": 120.7,
    "Venus": 250.4,
    "Saturn": 330.6,
    "Rahu": 195.0,
    "Ketu": 15.0
}

# -----------------------------
# Print assignments (verification)
# -----------------------------
print("Planet -> degree -> house assignment")
for pname, pdata in sample_planets.items():
    h = get_house_number_from_degree(pdata, sample_house_cusps)
    print(f"{pname:8} -> {pdata:7.3f}° -> House {h}")

print("\nHouse cusps (for reference):")
for i, c in enumerate(sample_house_cusps, start=1):
    print(f"House {i:2}: {c:.6f}°")



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

# ---------- East-Indian Chart Helpers ----------
def _planet_abbr(name: str) -> str:
    mapping = {
        'Sun': 'SUN', 'Moon': 'MOO', 'Mars': 'MAR', 'Mercury': 'MER',
        'Jupiter': 'JUP', 'Venus': 'VEN', 'Saturn': 'SAT',
        'Rahu': 'RAH', 'Ketu': 'KET'
    }
    return mapping.get(name, name[:3].upper())

def create_east_indian_chart_drawing(planet_data, house_cusps_degrees):
    """
    Vector drawing kept for compatibility; PNG rendering uses Pillow instead.
    """
    size = 440
    margin = 24
    inner = size - 2 * margin
    cell = inner / 3.0

    d = Drawing(size, size)
    d.add(Rect(6, 6, size - 12, size - 12, strokeColor=colors.black, fillColor=None, strokeWidth=6))
    ox, oy = margin, margin
    d.add(Rect(ox, oy, inner, inner, strokeColor=colors.black, fillColor=None, strokeWidth=2))

    # grid lines
    for i in range(1, 3):
        d.add(Line(ox + i * cell, oy, ox + i * cell, oy + inner, strokeColor=colors.black, strokeWidth=1.5))
        d.add(Line(ox, oy + i * cell, ox + inner, oy + i * cell, strokeColor=colors.black, strokeWidth=1.5))

    # diagonals (same pattern)
    x0, x1, x2, x3 = ox, ox+cell, ox+2*cell, ox+3*cell
    y0, y1, y2, y3 = oy, oy+cell, oy+2*cell, oy+3*cell
    d.add(Line(x0, y3, x1, y2, strokeColor=colors.black, strokeWidth=1.5))
    d.add(Line(x3, y3, x2, y2, strokeColor=colors.black, strokeWidth=1.5))
    d.add(Line(x0, y0, x1, y1, strokeColor=colors.black, strokeWidth=1.5))
    d.add(Line(x3, y0, x2, y1, strokeColor=colors.black, strokeWidth=1.5))

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

    houses = {i: [] for i in range(1, 13)}
    for pname, pdata in planet_data.items():
        hnum = get_house_number_from_degree(pdata['full_degree'], house_cusps_degrees)
        houses[hnum].append(_planet_abbr(pname))

    for h in range(1, 13):
        x, y, anchor = positions.get(h, (ox + 1.5*cell, oy + 1.5*cell, 'middle'))
        if houses[h]:
            text = ", ".join(houses[h])
            font_size = 11 if len(text) < 12 else 9
            d.add(String(x, y, text, fontSize=font_size, fillColor=colors.darkblue,
                         textAnchor=anchor, fontName="Helvetica-Bold"))
    return d

# ---------- Pillow renderer (robust fallback) ----------
def render_chart_png_bytes_pil(planet_data, house_cusps_degrees, size=900, out_path=None,
                              show_degrees=True, show_signs=False, save_file=False):
    """
    Render East-Indian chart as PNG bytes.

    - planet_data: dict of planet -> { ..., 'full_degree': float, 'sign': str, 'degree': 'xx.xx°', ... }
    - house_cusps_degrees: list of 12 cusp degrees (0..360)
    - size: image size in pixels (square)
    - out_path: optional file path to save PNG
    - show_degrees: if True, show planet degree (like "14.23°") next to the planet label
    - show_signs: if True, show sign short name after label (e.g. "SUN (Aries)")
    - save_file: if True and out_path provided, save file to out_path (also returns bytes)
    Returns: PNG bytes
    """
    from PIL import Image, ImageDraw, ImageFont
    import io

    pad = int(size * 0.05)
    inner = size - 2 * pad
    cell = inner / 3.0
    ox, oy = pad, pad
    bg = (255, 255, 255)
    line_color = (0, 0, 0)
    planet_color = (2, 48, 99)
    house_num_color = (40, 40, 40)
    small_text_color = (70, 70, 70)

    im = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(im)

    # outer border + inner square
    draw.rectangle([pad // 4, pad // 4, size - pad // 4, size - pad // 4], outline=line_color,
                   width=max(2, int(size * 0.01)))
    draw.rectangle([ox, oy, ox + inner, oy + inner], outline=line_color, width=max(1, int(size * 0.003)))

    # vertical & horizontal grid lines
    for i in range(1, 3):
        x = ox + i * cell; y = oy + i * cell
        draw.line([(x, oy), (x, oy + inner)], fill=line_color, width=max(1, int(size * 0.003)))
        draw.line([(ox, y), (ox + inner, y)], fill=line_color, width=max(1, int(size * 0.003)))

    # diagonals
    x0, x1, x2, x3 = ox, ox + cell, ox + 2 * cell, ox + 3 * cell
    y0, y1, y2, y3 = oy, oy + cell, oy + 2 * cell, oy + 3 * cell
    draw.line([(x0, y3), (x1, y2)], fill=line_color, width=max(1, int(size * 0.003)))
    draw.line([(x3, y3), (x2, y2)], fill=line_color, width=max(1, int(size * 0.003)))
    draw.line([(x0, y0), (x1, y1)], fill=line_color, width=max(1, int(size * 0.003)))
    draw.line([(x3, y0), (x2, y1)], fill=line_color, width=max(1, int(size * 0.003)))

    # positions for planet text inside house squares (tweaked for visual balance)
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

    # Build houses -> list of planet labels (use full_degree correctly)
    houses = {i: [] for i in range(1, 13)}
    for pname, pdata in planet_data.items():
        full_deg = pdata.get('full_degree') if isinstance(pdata, dict) else pdata
        hnum = get_house_number_from_degree(full_deg, house_cusps_degrees)
        label = _planet_abbr(pname)
        extras = []
        if show_degrees:
            deg_text = pdata.get('degree') or f"{(full_deg % 30):.2f}°"
            extras.append(deg_text)
        if show_signs:
            extras.append(pdata.get('sign', ''))
        if extras:
            label = f"{label} {' '.join(extras)}"
        houses[hnum].append((pname, label))

    # fonts (try to load DejaVu; fallback to PIL default)
    try:
        house_font_size = max(10, int(size * 0.018))
        planet_font_size = max(11, int(size * 0.030))
        font_house = ImageFont.truetype("DejaVuSans-Bold.ttf", size=house_font_size)
        font_planet = ImageFont.truetype("DejaVuSans-Bold.ttf", size=planet_font_size)
        font_small = ImageFont.truetype("DejaVuSans.ttf", size=max(9, int(size * 0.014)))
    except Exception:
        font_house = ImageFont.load_default()
        font_planet = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # -----------------------
    # Draw only house #1 (bottom center). Remove other house numbers.
    # -----------------------
    # compute house 1 position (use same anchor as positions[1])
    try:
        h1_x, h1_y, _ = positions.get(1, (ox + 1.5*cell, oy + 2.68*cell, 'center'))
    except Exception:
        h1_x, h1_y = (ox + 1.5*cell, oy + 2.68*cell)

    label = "1"
    try:
        hb = draw.textbbox((0, 0), label, font=font_house)
        hw, hh = hb[2] - hb[0], hb[3] - hb[1]
    except AttributeError:
        hw, hh = draw.textsize(label, font=font_house)

    # clamp inside inner square
    margin = max(6, int(size * 0.01))
    min_x = ox + margin
    max_x = ox + inner - margin - hw
    min_y = oy + margin
    max_y = oy + inner - margin - hh
    tx = max(min_x, min(h1_x - hw / 2, max_x))
    ty = max(min_y, min(h1_y - hh / 2, max_y))

    # draw subtle background for readability and then the number
    try:
        draw.rectangle([tx - 4, ty - 2, tx + hw + 4, ty + hh + 2], fill=bg)
    except Exception:
        pass
    draw.text((tx, ty), label, fill=house_num_color, font=font_house)

    # draw planets inside houses (stack if multiple)
    for h in range(1, 13):
        items = houses[h]
        if not items:
            continue
        x, y, anchor = positions.get(h, (ox + 1.5*cell, oy + 1.5*cell, 'center'))
        labels = [lab for (_, lab) in items]
        # compute total height to vertically center the stack
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
                w = bbox[2] - bbox[0]; hgt = bbox[3] - bbox[1]
            except AttributeError:
                w, hgt = draw.textsize(lab, font=font_planet)
            if anchor == 'left':
                txp = x
            elif anchor == 'right':
                txp = x - w
            else:
                txp = x - (w / 2.0)
            draw.text((txp, cur_y), lab, fill=planet_color, font=font_planet)
            # small bullet to the left of label
            try:
                circle_r = max(3, int(size * 0.006))
                draw.ellipse((txp - circle_r*2 - 2, cur_y + hgt/2 - circle_r, txp - 2, cur_y + hgt/2 + circle_r),
                             fill=planet_color)
            except Exception:
                pass
            cur_y += hgt + int(size * 0.01)

    # small legend / note at bottom (optional)
    note = "House 1 shown. Other house numbers are hidden. Generated by AstroGen."
    try:
        nb = draw.textbbox((0, 0), note, font=font_small)
        nw = nb[2] - nb[0]; nh = nb[3] - nb[1]
    except AttributeError:
        nw, nh = draw.textsize(note, font=font_small)
    draw.text((size - pad - nw, size - pad + 2), note, fill=small_text_color, font=font_small)

    # save to bytes
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    if save_file and out_path:
        try:
            with open(out_path, "wb") as f:
                f.write(png_bytes)
        except Exception:
            pass

    return png_bytes


# ---------- PDF Generation ----------
def generate_pdf_report(birth_data, chart_data):
    """Generate a professional PDF report (embed Pillow-generated PNG)"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
                                 fontSize=24, textColor=colors.HexColor('#8B4513'),
                                 alignment=TA_CENTER, spaceAfter=12)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'],
                                   fontSize=14, textColor=colors.HexColor('#FF8C00'),
                                   spaceAfter=10, spaceBefore=12)

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

    # East Indian Chart (embed Pillow PNG)
    story.append(Paragraph("Lagna Chart (East Indian Style)", heading_style))
    png_bytes = render_chart_png_bytes_pil(chart_data['planets'], chart_data['house_cusps_degrees'], size=1200)
    img_io = io.BytesIO(png_bytes)
    img = RLImage(img_io, width=4.8*inch, height=4.8*inch)
    story.append(img)
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

    # House cusps
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

    # Dasha
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
# (Use your polished form code; unchanged except chart rendering usage below)
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
    .stTextInput>div>div>input, .stTextInput>div>div>textarea {
        background: rgba(255,255,255,0.02) !important;
        border-radius: 8px !important;
        padding: 14px 12px !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        color: #e6e6e6 !important;
        font-size: 15px !important;
    }
    .stSelectbox>div>div>div>div, .stMultiSelect>div>div>div>div {
        border-radius: 8px !important;
        padding: 8px 10px !important;
        background: rgba(255,255,255,0.02) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        color: #e6e6e6;
        font-size: 15px;
    }
    .stRadio .css-1r6slb0 { gap: 12px; }
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

st.markdown('<div class="card"><h2>Enter your birth details</h2><div class="muted">Provide accurate date, time and place for best results</div></div>', unsafe_allow_html=True)

with st.form("birth_form", clear_on_submit=False):
    left_col, right_col = st.columns([2, 1.15], gap="medium")
    with left_col:
        dob_str = st.text_input("Date of Birth (DD/MM/YYYY)", value="", placeholder="e.g., 23/09/1994", help="Enter date in format DD/MM/YYYY")
        place = st.text_input("Place of Birth", value="", placeholder="e.g., Mumbai, India", help="City, Country (for geocoding)")
        gender = st.selectbox("Gender", ["Male", "Female", "Other"], label_visibility="visible")

    with right_col:
        st.write("**Time of Birth**")
        tcols = st.columns([1.1, 1.1, 1.2], gap="small")
        hour_12 = tcols[0].text_input("Hour (1-12)", value="", max_chars=2, placeholder="HH")
        minute = tcols[1].text_input("Minute (0-59)", value="", max_chars=2, placeholder="MM")
        # label_visibility collapsed to avoid accessibility warning while still providing a label in code
        am_pm = tcols[2].radio("Meridian", ["AM", "PM"], horizontal=True, label_visibility="collapsed")
        st.write("")  # spacer

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

    if submitted:
        dob = _validated_date(dob_str)
        if dob is None:
            st.error("⚠️ Enter a valid date in DD/MM/YYYY format (for example: 23/09/1994).")
        else:
            try:
                h = int(hour_12)
                m = int(minute)
                if not (1 <= h <= 12) or not (0 <= m <= 59):
                    raise ValueError()
            except Exception:
                st.error("⚠️ Enter valid time: hour 1-12 and minute 0-59.")
                dob = None

        if dob is not None:
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

# Additional validation block (keeps your prior checks)
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

# ---------- Moonshine · Lagna · Sunshine Summary (insert BEFORE chart generation) ----------
def _deg_to_sign_text(deg):
    """Return (sign_name, deg_in_sign_float, deg_text). deg in 0..360"""
    signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
             'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
    deg = float(deg) % 360.0
    sign_index = int(deg // 30)
    deg_in_sign = deg - (sign_index * 30)
    d = int(deg_in_sign)
    minutes = int(round((deg_in_sign - d) * 60))
    if minutes == 60:
        d += 1
        minutes = 0
    deg_text = f"{d}°{minutes:02d}'"
    return signs[sign_index], deg_in_sign, deg_text

def _compute_jd_from_local_using_place(dob_date, tob_time, place_str):
    """
    Build a UTC datetime using geocoded timezone (via your helpers) then return swe.julday(UT).
    Returns (jd_ut, tz_name, lat, lng) or (None, None, None, None) on failure.
    """
    try:
        lat, lng = get_coordinates(place_str)
        if lat is None or lng is None:
            return None, None, None, None
        # combine naive local date+time
        local_dt = datetime.combine(dob_date, tob_time)
        # get tz name via timezonefinder
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lat=lat, lng=lng)
        if not tz_name:
            # fallback: use UTC offset helper
            offset_hours = get_timezone_offset(lat, lng, local_dt)
            utc_dt = local_dt - timedelta(hours=offset_hours)
        else:
            tz = pytz.timezone(tz_name)
            if local_dt.tzinfo is None:
                local_dt = tz.localize(local_dt)
            utc_dt = local_dt.astimezone(pytz.utc)
        year, month, day = utc_dt.year, utc_dt.month, utc_dt.day
        hour_decimal = utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0 + utc_dt.microsecond / 3_600_000_000.0
        jd_ut = swe.julday(year, month, day, hour_decimal, swe.GREG_CAL)
        return jd_ut, tz_name, lat, lng
    except Exception:
        return None, None, None, None

def _calc_planet_longitude(jd_ut, planet_const):
    """Return ecliptic longitude (0..360) for given planet constant."""
    try:
        res = swe.calc_ut(jd_ut, planet_const, swe.FLG_SIDEREAL)
        # common shapes: ([lon, lat, dist], flag) or [lon,lat,dist]
        if isinstance(res, (list, tuple)):
            if isinstance(res[0], (list, tuple)):
                lon = res[0][0]
            else:
                lon = res[0]
        else:
            lon = float(res)
        return float(lon) % 360.0
    except Exception:
        return None

def _calc_ascendant(jd_ut, lat, lng):
    """Return ascendant longitude (0..360)."""
    try:
        cusps, ascmc = swe.houses(jd_ut, lat, lng)
        asc = ascmc[0]
        return float(asc) % 360.0
    except Exception:
        return None

def build_moon_lagna_sun_summary_for_birth(dob_date, tob_time, place_str):
    """
    Returns dict with 'sun', 'moon', 'lagna' each containing sign, deg_text and interp,
    or (None, error_message) on failure.
    """
    jd_ut, tz_name, lat, lng = _compute_jd_from_local_using_place(dob_date, tob_time, place_str)
    if jd_ut is None:
        return None, "Could not compute time/zone for the provided place."

    sun_lon = _calc_planet_longitude(jd_ut, swe.SUN)
    moon_lon = _calc_planet_longitude(jd_ut, swe.MOON)
    asc_lon = _calc_ascendant(jd_ut, lat, lng)

    if None in (sun_lon, moon_lon, asc_lon):
        return None, "Error computing planetary positions; check swisseph installation."

    sun_sign, sun_deg_in_sign, sun_deg_text = _deg_to_sign_text(sun_lon)
    moon_sign, moon_deg_in_sign, moon_deg_text = _deg_to_sign_text(moon_lon)
    asc_sign, asc_deg_in_sign, asc_deg_text = _deg_to_sign_text(asc_lon)

    # one-line interpretations (templates)
    sun_interp = f"Sun ({sun_sign} {sun_deg_text}) — core identity and vitality. {sun_sign} energy shows strongly in your persona."
    moon_interp = f"Moon ({moon_sign} {moon_deg_text}) — emotions and inner life. {moon_sign} Moon colours your instincts and moods."
    asc_interp = f"Lagna / Ascendant ({asc_sign} {asc_deg_text}) — outward style and first impressions. You present as {asc_sign} rising."

    return {
        "sun": {"sign": sun_sign, "deg_text": sun_deg_text, "interp": sun_interp},
        "moon": {"sign": moon_sign, "deg_text": moon_deg_text, "interp": moon_interp},
        "lagna": {"sign": asc_sign, "deg_text": asc_deg_text, "interp": asc_interp},
        "tz_name": tz_name,
        "lat": lat, "lng": lng
    }, None

# ---------- Moonshine · Lagna · Sunshine Summary (auto-show BEFORE chart generation) ----------
try:
    summary, err = build_moon_lagna_sun_summary_for_birth(
        birth_data['dob'], birth_data['tob'], birth_data['place']
    )
    if err:
        st.error(f"⚠️ {err}")
    else:
        st.markdown("### Moonshine · Lagna · Sunshine Summary")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric(label="🌞 Sunshine (Sun)", value=f"{summary['sun']['sign']} {summary['sun']['deg_text']}")
            st.write(summary['sun']['interp'])
        with c2:
            st.metric(label="🌙 Moonshine (Moon)", value=f"{summary['moon']['sign']} {summary['moon']['deg_text']}")
            st.write(summary['moon']['interp'])
        with c3:
            st.metric(label="🜁 Lagna (Ascendant)", value=f"{summary['lagna']['sign']} {summary['lagna']['deg_text']}")
            st.write(summary['lagna']['interp'])
        # show resolved tz if available
        if summary.get('tz_name'):
            st.caption(f"Timezone used for calculation: {summary['tz_name']} (lat: {summary['lat']:.3f}, lng: {summary['lng']:.3f})")
except Exception as e:
    st.error(f"⚠️ Error generating summary: {e}")
# -------------------------------------------------------------------------------------

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

# ---------- East-Indian Chart (UI) ----------
st.markdown("### 🌙 Your Complete KP Chart")
with st.container():
    st.markdown("#### East Indian Chart")
    # Use Pillow-based PNG (robust on cloud)
    try:
        png = render_chart_png_bytes_pil(chart['planets'], chart['house_cusps_degrees'], size=900)
        # use width='stretch' to match use_container_width=True behavior
        st.image(png, width='stretch')
    except Exception as e:
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
            width='stretch'  # replaced use_container_width=True
        )
    except Exception as e:
        st.error(f"⚠️ PDF generation error: {e}")

# ---------- AI Agent Prompts ----------
AGENTS = {
    "overall": """You are an expert KP (Krishnamurti Paddhati) astrologer with deep knowledge of Vedic astrology.
...
"""  # keep your original AGENTS content here
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
    if st.button("🌟 Overall Life", width='stretch'):
        st.session_state["overall_result"] = get_ai_reading("overall")
with col2:
    if st.button("💼 Career", width='stretch'):
        st.session_state["career_result"] = get_ai_reading("career")
with col3:
    if st.button("💖 Relationship", width='stretch'):
        st.session_state["relationship_result"] = get_ai_reading("relationship")

if "overall_result" in st.session_state:
    st.markdown("#### 🌟 Overall Life Reading")
    with st.container():
        st.markdown(st.session_state["overall_result"])

if "career_result" in st.session_state:
    st.markdown("#### 💼 Career Reading")
    with st.container():
        st.markdown(st.session_state["career_result"])

if "relationship_result" in st.session_state:
    st.markdown("#### 💖 Relationship Reading")
    with st.container():
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
