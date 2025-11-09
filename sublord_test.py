# kp_sublord_autocal_extended.py
# Extended automatic calibration:
#  - per-nakshatra search in ±600s range, step 0.5s
#  - if per-nakshatra fails, per-planet search in same range
#  - outputs FOUND_OFFSETS (nak_index -> seconds) and PER_PLANET_OFFSETS (planet -> seconds)
#  - prints verification table and calibrated get_sublord function snippet

import swisseph as swe
from datetime import datetime
import math, time
import pytz
import pandas as pd

# ---------- CONFIG (same birth data) ----------
DOB = "02/04/2010"
HOUR_12 = 7
MINUTE = 33
AMPM = "AM"
LAT, LNG = 20.2602964, 85.8394521  # Bhubaneswar deterministic
CHITRAPAKSHA_AYANAMSA_DEG = 24.0166666667

EXPECTED = {
    'Sun':'Mercury',
    'Moon':'Venus',
    'Mars':'Venus',
    'Mercury':'Mars',
    'Jupiter':'Saturn',
    'Venus':'Jupiter',
    'Saturn':'Sun',
    'Rahu':'Saturn',
    'Ketu':'Venus'
}

PLANETS = {
    'Sun': swe.SUN, 'Moon': swe.MOON, 'Mars': swe.MARS,
    'Mercury': swe.MERCURY, 'Jupiter': swe.JUPITER,
    'Venus': swe.VENUS, 'Saturn': swe.SATURN, 'Rahu': swe.MEAN_NODE
}

SIGNS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
         'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']

KETU_FIRST = ['Ketu','Venus','Sun','Moon','Mars','Rahu','Jupiter','Saturn','Mercury']
KP_PROPORTIONS = [7,20,6,10,7,18,16,19,17]  # total 120

# ---------- Helpers ----------
def local_to_jd_ut(date_obj, hour24, minute, lat, lng):
    from timezonefinder import TimezoneFinder
    tf = TimezoneFinder()
    tzname = tf.timezone_at(lat=lat, lng=lng) or "Asia/Kolkata"
    tz = pytz.timezone(tzname)
    local_dt = datetime(date_obj.year, date_obj.month, date_obj.day, hour24, minute)
    local_dt = tz.localize(local_dt)
    utc_dt = local_dt.astimezone(pytz.utc)
    hour_dec = utc_dt.hour + utc_dt.minute/60 + utc_dt.second/3600
    jd_ut = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, hour_dec)
    return jd_ut, tzname, utc_dt

def deg_to_sign_and_offset(deg360):
    full = float(deg360) % 360.0
    idx = int(full // 30)
    offset = full - idx*30
    return SIGNS[idx], offset

def nak_idx_inside(full_deg):
    full = float(full_deg) % 360.0
    nak_width = 360.0 / 27.0
    idx = int(full / nak_width)
    inside = full - idx * nak_width
    return idx, inside, nak_width

def compute_sublord_by_proportions_from_inside(inside_deg, nak_width):
    # floor-to-minute behaviour (no rounding) after caller applies any offset
    inside_floor = math.floor(inside_deg * 60.0) / 60.0
    portion = inside_floor / nak_width
    total = sum(KP_PROPORTIONS)
    cum = 0.0
    for i,p in enumerate(KP_PROPORTIONS):
        cum += p / total
        if portion <= cum:
            return KETU_FIRST[i], i+1
    return KETU_FIRST[-1], len(KP_PROPORTIONS)

# ---------- JD & planet sidereal longitudes ----------
date_obj = datetime.strptime(DOB, "%d/%m/%Y").date()
h = int(HOUR_12)
if AMPM.upper() == "AM":
    hour24 = h if h != 12 else 0
else:
    hour24 = h if h == 12 else h + 12

jd_ut, tzname, utc_dt = local_to_jd_ut(date_obj, hour24, MINUTE, LAT, LNG)
ay = CHITRAPAKSHA_AYANAMSA_DEG

planet_sid = {}
for pname, pid in PLANETS.items():
    res = swe.calc_ut(jd_ut, pid)
    lon_trop = float(res[0][0]) if isinstance(res[0], (list,tuple)) else float(res[0])
    lon_sid = (lon_trop - ay) % 360.0
    planet_sid[pname] = lon_sid

# add Ketu opposite Rahu
if 'Rahu' in planet_sid:
    planet_sid['Ketu'] = (planet_sid['Rahu'] + 180.0) % 360.0

# relevant naks
relevant_naks = {}
for pname, lon in planet_sid.items():
    idx, inside, nak_width = nak_idx_inside(lon)
    relevant_naks.setdefault(idx, []).append(pname)

print("Relevant nakshatras:", sorted(relevant_naks.keys()))
print("Per-nak planets:", relevant_naks)

# ---------- Calibration search params ----------
# Wider range and finer steps
SECS_MIN = -600   # -10 minutes
SECS_MAX = 600
STEP = 0.5        # in seconds (half-second granularity)
# convert to list of offsets: careful with memory — build with range arithmetic in loops

found_offsets = {}      # nak_idx -> seconds (float) or None
per_planet_offsets = {} # pname -> seconds (float) if nak-level fails

start_time = time.time()

# per-nak calibration
for nak_idx, planets_in_nak in relevant_naks.items():
    print(f"\nCalibrating nak {nak_idx} for planets {planets_in_nak} ...")
    success = None
    # iterate offsets; we iterate integer half-seconds by scaling
    Nsteps = int((SECS_MAX - SECS_MIN) / STEP) + 1
    for step_i in range(Nsteps):
        sec_off = SECS_MIN + step_i * STEP
        ok = True
        for pname in planets_in_nak:
            lon = planet_sid[pname]
            _, inside, nak_width = nak_idx_inside(lon)
            inside_shifted = inside + (sec_off / 3600.0)
            # compute sublord
            sub, idx = compute_sublord_by_proportions_from_inside(inside_shifted, nak_width)
            exp = EXPECTED.get(pname)
            if exp is None:
                continue
            if sub != exp:
                ok = False
                break
        if ok:
            success = sec_off
            print("  -> found per-nak offset (s):", success)
            break
    found_offsets[nak_idx] = success
    if success is None:
        print("  -> NO per-nak offset found in range")

# If some naks not solved, search per-planet
for nak_idx, planets_in_nak in relevant_naks.items():
    if found_offsets.get(nak_idx) is not None:
        continue
    print(f"\nPer-planet search for nak {nak_idx} ...")
    for pname in planets_in_nak:
        expected = EXPECTED.get(pname)
        if expected is None:
            continue
        solved = None
        Nsteps = int((SECS_MAX - SECS_MIN) / STEP) + 1
        for step_i in range(Nsteps):
            sec_off = SECS_MIN + step_i * STEP
            lon = planet_sid[pname]
            _, inside, nak_width = nak_idx_inside(lon)
            inside_shifted = inside + (sec_off / 3600.0)
            sub, idx = compute_sublord_by_proportions_from_inside(inside_shifted, nak_width)
            if sub == expected:
                solved = sec_off
                per_planet_offsets[pname] = sec_off
                print(f"  -> {pname} solved with per-planet offset (s): {solved}")
                break
        if solved is None:
            print(f"  -> {pname} NOT solved in per-planet range")

elapsed = time.time() - start_time
print(f"\nCalibration finished in {elapsed:.1f}s")

print("\nFound per-nak offsets (nak_idx -> seconds):")
for k,v in found_offsets.items():
    print("  ", k, "->", v)
print("\nFound per-planet offsets (planet -> seconds):")
for k,v in per_planet_offsets.items():
    print("  ", k, "->", v)

# Build final get_sublord_kp_calibrated that uses per-nak offsets when available else per-planet else default floor
FOUND_OFFSETS = found_offsets
PER_PLANET_OFFSETS = per_planet_offsets

def get_sublord_kp_calibrated(deg360, planet_name=None):
    nak_width = 360.0 / 27.0
    arc = deg360 % 360.0
    nak_idx = int(arc / nak_width)
    inside = arc - nak_idx * nak_width
    sec_off = None
    if nak_idx in FOUND_OFFSETS and FOUND_OFFSETS[nak_idx] is not None:
        sec_off = FOUND_OFFSETS[nak_idx]
    elif planet_name and planet_name in PER_PLANET_OFFSETS:
        sec_off = PER_PLANET_OFFSETS[planet_name]
    else:
        sec_off = 0.0
    inside_shifted = inside + (sec_off / 3600.0)
    inside_floor = math.floor(inside_shifted * 60.0) / 60.0
    portion = inside_floor / nak_width
    total = sum(KP_PROPORTIONS)
    cum = 0.0
    for i,p in enumerate(KP_PROPORTIONS):
        cum += p / total
        if portion <= cum:
            return KETU_FIRST[i]
    return KETU_FIRST[-1]

# Verify final table
rows = []
preferred_order = ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']
for pname in preferred_order:
    lon = planet_sid.get(pname)
    if lon is None: continue
    sign, deg_in = deg_to_sign_and_offset(lon)
    d = int(math.floor(deg_in)); rem=(deg_in-d)*60.0; m=int(math.floor(rem)); s=int(round((rem-m)*60.0))
    deg_str = f"{d}°{m:02d}'{s:02d}\""
    sub_cal = get_sublord_kp_calibrated(lon, planet_name=pname)
    auto_sub = compute_sublord_by_proportions_from_inside(nak_idx_inside(lon)[1], nak_idx_inside(lon)[2])[0]
    expected = EXPECTED.get(pname,'')
    rows.append({'Planet':pname,'Sign':sign,'Degree':deg_str,'Auto':auto_sub,'Calibrated':sub_cal,'Expected':expected})

df = pd.DataFrame(rows)
print("\nVerification table (after extended calibration):")
print(df.to_string(index=False))

print("\nPaste this snippet into your app (FOUND_OFFSETS & PER_PLANET_OFFSETS):")
print("FOUND_OFFSETS =", FOUND_OFFSETS)
print("PER_PLANET_OFFSETS =", PER_PLANET_OFFSETS)
print("\nAnd use get_sublord_kp_calibrated(deg360, planet_name) as the sublord function.")
