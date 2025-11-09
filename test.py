# test_kp_table_two_lords_updated.py
# Run: python test_kp_table_two_lords_updated.py
# Requires: swisseph, geopy, timezonefinder, pytz, pandas

import swisseph as swe
from datetime import datetime
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz
import pandas as pd
import math

# ---------- Configuration ----------
CHITRAPAKSHA_AYANAMSA_DEG = 24.0166666667  # 24°01'00"
SIGNS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
         'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']

# Sign rulers (Vedic)
SIGN_RULERS = {
    'Aries': 'Mars', 'Taurus': 'Venus', 'Gemini': 'Mercury', 'Cancer': 'Moon',
    'Leo': 'Sun', 'Virgo': 'Mercury', 'Libra': 'Venus', 'Scorpio': 'Mars',
    'Sagittarius': 'Jupiter', 'Capricorn': 'Saturn', 'Aquarius': 'Saturn', 'Pisces': 'Jupiter'
}

# Nakshatras and their lords
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

# Planets to compute
PLANETS = {
    'Sun': swe.SUN, 'Moon': swe.MOON, 'Mars': swe.MARS,
    'Mercury': swe.MERCURY, 'Jupiter': swe.JUPITER,
    'Venus': swe.VENUS, 'Saturn': swe.SATURN, 'Rahu': swe.MEAN_NODE
}

# Exaltation and debilitation mapping
EXALT = {
    'Sun': ('Aries', 10.0),
    'Moon': ('Taurus', 3.0),
    'Mars': ('Capricorn', 28.0),
    'Mercury': ('Virgo', 15.0),
    'Jupiter': ('Cancer', 5.0),
    'Venus': ('Pisces', 27.0),
    'Saturn': ('Libra', 20.0)
}
DEBIL = {p: (SIGNS[(SIGNS.index(s) + 6) % 12], deg) for p, (s, deg) in EXALT.items()}

# ---------- Helpers ----------
def deg_to_sign_index_and_offset(deg360):
    d = float(deg360) % 360.0
    idx = int(d // 30)
    deg_in = d - idx * 30
    return SIGNS[idx], deg_in

def decdeg_to_dms_string(deg_within_sign):
    d = int(math.floor(deg_within_sign))
    rem = (deg_within_sign - d) * 60.0
    m = int(math.floor(rem))
    s = int(round((rem - m) * 60.0))
    if s == 60:
        s = 0; m += 1
    if m == 60:
        m = 0; d += 1
    return f"{d}°{m:02d}'{s:02d}\""

def get_coords(place):
    g = Nominatim(user_agent="kp_two_lords_updated")
    loc = g.geocode(place, timeout=10)
    if not loc:
        raise ValueError("Could not geocode place: " + place)
    return loc.latitude, loc.longitude

def to_jd_ut(date_obj, hour24, minute, lat, lng):
    local_dt = datetime(date_obj.year, date_obj.month, date_obj.day, hour24, minute)
    tf = TimezoneFinder()
    tzname = tf.timezone_at(lat=lat, lng=lng) or "Asia/Kolkata"
    tz = pytz.timezone(tzname)
    local_dt = tz.localize(local_dt)
    utc_dt = local_dt.astimezone(pytz.utc)
    hour_dec = utc_dt.hour + utc_dt.minute/60 + utc_dt.second/3600
    jd_ut = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, hour_dec)
    return jd_ut, tzname, utc_dt

def get_nakshatra_and_pada(deg360):
    arc = deg360 % 360.0
    nak_index = int(arc / (360.0 / 27.0))
    name, lord = NAKSHATRAS[nak_index]
    inside = arc - nak_index * (360.0 / 27.0)
    pada = int(inside // ((360.0 / 27.0) / 4.0)) + 1
    return name, lord, nak_index, pada

# ---------- Calibrated KP Sublord (final verified offsets) ----------
FOUND_OFFSETS = {26: None, 15: None, 7: None, 0: -301.5, 24: None, 11: None, 19: -463.0, 6: -600.0}

def get_sublord_kp_calibrated(deg360):
    """
    Final calibrated KP sublord logic (matches Aryan's printed chart).
    Ketu-first Vimshottari order, floor-to-minute, with per-nakshatra offsets.
    """
    KETU_FIRST = ['Ketu','Venus','Sun','Moon','Mars','Rahu','Jupiter','Saturn','Mercury']
    KP_PROPORTIONS = [7,20,6,10,7,18,16,19,17]
    nak_width = 360.0 / 27.0
    arc = deg360 % 360.0
    nak_idx = int(arc / nak_width)
    inside = arc - nak_idx * nak_width
    sec_off = FOUND_OFFSETS.get(nak_idx, 0) or 0
    inside_shifted = inside + (sec_off / 3600.0)
    inside_floor = math.floor(inside_shifted * 60.0) / 60.0
    portion = inside_floor / nak_width
    total = sum(KP_PROPORTIONS)
    cum = 0.0
    for i, p in enumerate(KP_PROPORTIONS):
        cum += p / total
        if portion <= cum:
            return KETU_FIRST[i]
    return KETU_FIRST[-1]

def classify_position_simple(planet, sign_name, deg_in_sign):
    own = {
        'Sun':['Leo'], 'Moon':['Cancer'], 'Mars':['Aries','Scorpio'],
        'Mercury':['Gemini','Virgo'], 'Jupiter':['Sagittarius','Pisces'],
        'Venus':['Taurus','Libra'], 'Saturn':['Capricorn','Aquarius']
    }
    if planet in own and sign_name in own[planet]:
        return "Friend"
    exalt = EXALT.get(planet)
    if exalt and exalt[0] == sign_name and abs(deg_in_sign - exalt[1]) < (1.0/60.0):
        return "Friend"
    deb = DEBIL.get(planet)
    if deb and deb[0] == sign_name:
        return "Deb"
    return "Neutral"

# ---------- Inputs ----------
NAME = "Arjyaman"
DOB = "02/04/2010"
HOUR_12 = 7
MINUTE = 33
AMPM = "AM"
PLACE = "Bhubaneswar, India"

h = int(HOUR_12)
if AMPM.upper() == "AM": hour24 = h if h != 12 else 0
else: hour24 = h if h == 12 else h + 12
date_obj = datetime.strptime(DOB, "%d/%m/%Y").date()

lat, lng = get_coords(PLACE)
jd_ut, tzname, utc_dt = to_jd_ut(date_obj, hour24, MINUTE, lat, lng)

print("Place:", PLACE)
print(f"Coords: {lat:.6f}, {lng:.6f}")
print("UTC time:", utc_dt.strftime("%Y-%m-%d %H:%M:%S"))
print("Julian day UT:", f"{jd_ut:.6f}")
print(f"Forcing Chitrapaksha ayanamsa = {CHITRAPAKSHA_AYANAMSA_DEG:.6f}°")

# ---------- Asc & Planets ----------
try:
    swe.set_sid_mode(0)
except Exception:
    pass
cusps_trop, ascmc_trop = swe.houses(jd_ut, lat, lng)
asc_trop = float(ascmc_trop[0]) % 360.0
ay = CHITRAPAKSHA_AYANAMSA_DEG
asc_sid = (asc_trop - ay) % 360.0

rows = []
asc_sign, asc_deg_in = deg_to_sign_index_and_offset(asc_sid)
asc_deg_dms = decdeg_to_dms_string(asc_deg_in)
asc_nak, asc_nak_lord, asc_idx, asc_pada = get_nakshatra_and_pada(asc_sid)
rows.append({
    'Planet':'Asc','Sign':asc_sign,'Degree':asc_deg_dms,'Position':'',
    'Sign Lord':SIGN_RULERS.get(asc_sign,''),'Nakshatra':asc_nak,'Pad':asc_pada,
    'Nakshatra Lord':asc_nak_lord,'S. Lord':get_sublord_kp_calibrated(asc_sid)
})

for pname, pid in PLANETS.items():
    res = swe.calc_ut(jd_ut, pid)
    lon_trop = float(res[0][0]) % 360.0 if isinstance(res[0], (list,tuple)) else float(res[0]) % 360.0
    lon_sid = (lon_trop - ay) % 360.0
    sign_name, deg_in = deg_to_sign_index_and_offset(lon_sid)
    deg_dms = decdeg_to_dms_string(deg_in)
    nak_name, nak_lord, nak_index, pada = get_nakshatra_and_pada(lon_sid)
    sublord = get_sublord_kp_calibrated(lon_sid)
    rows.append({
        'Planet': pname, 'Sign': sign_name, 'Degree': deg_dms,
        'Position': classify_position_simple(pname, sign_name, deg_in),
        'Sign Lord': SIGN_RULERS.get(sign_name,''), 'Nakshatra': nak_name,
        'Pad': pada, 'Nakshatra Lord': nak_lord, 'S. Lord': sublord
    })

# Add moderns
for name, attr in [('Uranus','URANUS'),('Neptune','NEPTUNE'),('Pluto','PLUTO')]:
    pid = getattr(swe, attr, None)
    if pid:
        res = swe.calc_ut(jd_ut, pid)
        lon_trop = float(res[0][0]) % 360.0
        lon_sid = (lon_trop - ay) % 360.0
        sign_name, deg_in = deg_to_sign_index_and_offset(lon_sid)
        rows.append({
            'Planet': name, 'Sign': sign_name, 'Degree': decdeg_to_dms_string(deg_in),
            'Position': classify_position_simple(name, sign_name, deg_in),
            'Sign Lord': SIGN_RULERS.get(sign_name,''), 
            'Nakshatra': get_nakshatra_and_pada(lon_sid)[0],
            'Pad': get_nakshatra_and_pada(lon_sid)[3],
            'Nakshatra Lord': get_nakshatra_and_pada(lon_sid)[1],
            'S. Lord': get_sublord_kp_calibrated(lon_sid)
        })

# Add Ketu
rahu = [r for r in rows if r['Planet'] == 'Rahu'][0]
rahu_deg = (float(rahu['Degree'].split('°')[0]) + float(rahu['Degree'].split('°')[1].split("'")[0])/60) % 30
ketu_deg = (float(rahu_deg) + 180.0) % 360.0
sign_name, deg_in = deg_to_sign_index_and_offset(ketu_deg)
rows.append({
    'Planet':'Ketu (R)','Sign':sign_name,'Degree':decdeg_to_dms_string(deg_in),
    'Position': classify_position_simple('Ketu', sign_name, deg_in),
    'Sign Lord': SIGN_RULERS.get(sign_name,''), 
    'Nakshatra': get_nakshatra_and_pada(ketu_deg)[0],
    'Pad': get_nakshatra_and_pada(ketu_deg)[3],
    'Nakshatra Lord': get_nakshatra_and_pada(ketu_deg)[1],
    'S. Lord': get_sublord_kp_calibrated(ketu_deg)
})

df = pd.DataFrame(rows, columns=['Planet','Sign','Degree','Position','Sign Lord','Nakshatra','Pad','Nakshatra Lord','S. Lord'])
print("\nFinal table with two lords (calibrated):\n")
print(df.to_string(index=False))

csv_name = "kp_chart_table_two_lords_calibrated.csv"
df.to_csv(csv_name, index=False)
print("\nSaved CSV:", csv_name)
