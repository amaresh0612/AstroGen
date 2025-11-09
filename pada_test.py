# find_offset_for_padas.py
import math

# --- Configuration: put your current computed planet longitudes here (full 0..360) ---
# Use the same longitudes you used in the tests earlier.
PLANETS = {
    'Asc': 21 + 38/60 + 51/3600 + 0*30,        # Aries 21:38:51 -> 21.6475 (Aries)
    'Sun': (18 + 19/60 + 19/3600) + 11*30,     # Pisces 18:19:19 -> add 11*30
    'Moon': (27 + 47/60 + 21/3600) + 6*30,     # Libra 27:47:21
    'Mars': (9 + 8/60 + 38/3600) + 3*30,       # Cancer 9:08:38
    'Mercury': (5 + 22/60 + 14/3600) + 0*30,   # Aries 5:22:14
    'Venus': (7 + 45/60 + 34/3600) + 0*30,     # Aries 7:45:34
    'Jupiter': (23 + 35/60 + 27/3600) + 10*30, # Aquarius 23:35:27 (10*30)
    'Saturn': (6 + 31/60 + 3/3600) + 5*30,     # Virgo 6:31:03 (5*30)
    'Rahu': (22 + 51/60 + 15/3600) + 8*30,     # Sagittarius 22:51:15 (8*30)
}
# If you already have Ketu you can compute or omit (we'll compute from Rahu)
PLANETS['Ketu'] = (PLANETS['Rahu'] + 180.0) % 360.0

# --- Expected padas from your printed chart (adjust if needed) ---
EXPECTED_PADAS = {
    'Asc': 3,
    'Sun': 1,
    'Moon': 2,
    'Mars': 1,
    'Mercury': 1,
    'Venus': 1,
    'Jupiter': 4,
    'Saturn': 4,
    'Rahu': 2,
    'Ketu': 3,
}

# --- Constants ---
NAK_WIDTH = 13.0 + 20.0/60.0  # 13°20' etc.
PADA_WIDTH = NAK_WIDTH / 4.0
EPS = 1e-9

NAKSHATRAS = [
    ('Ashwini','Ketu'), ('Bharani','Venus'), ('Krittika','Sun'), ('Rohini','Moon'),
    ('Mrigashira','Mars'), ('Ardra','Rahu'), ('Punarvasu','Jupiter'), ('Pushya','Saturn'),
    ('Ashlesha','Mercury'), ('Magha','Ketu'), ('Purva Phalguni','Venus'), ('Uttara Phalguni','Sun'),
    ('Hasta','Moon'), ('Chitra','Mars'), ('Swati','Rahu'), ('Vishakha','Jupiter'),
    ('Anuradha','Saturn'), ('Jyeshtha','Mercury'), ('Mula','Ketu'), ('Purva Ashadha','Venus'),
    ('Uttara Ashadha','Sun'), ('Shravana','Moon'), ('Dhanishta','Mars'), ('Shatabhisha','Rahu'),
    ('Purva Bhadrapada','Jupiter'), ('Uttara Bhadrapada','Saturn'), ('Revati','Mercury')
]

def norm(deg): return float(deg) % 360.0

def compute_pada_for_degree(deg360, rule='floor'):
    arc = norm(deg360)
    nak_idx = int(math.floor(arc / NAK_WIDTH))
    if nak_idx >= 27: nak_idx = 26
    inside = arc - (nak_idx * NAK_WIDTH)
    fraction = inside / PADA_WIDTH
    if rule == 'floor':
        # standard floor mapping
        if abs(round(fraction) - fraction) <= (EPS / PADA_WIDTH):
            fraction = round(fraction)
        pada = int(math.floor(fraction + EPS)) + 1
    else:
        # upper-inclusive variant
        if abs(round(fraction) - fraction) <= (EPS / PADA_WIDTH):
            fraction = round(fraction)
        pada = int(math.floor(fraction + EPS)) + 1
        if abs(fraction - round(fraction)) <= (EPS * 10) and fraction != 0:
            pada = int(round(fraction)) + 1
    if pada < 1: pada = 1
    if pada > 4: pada = 4
    return pada

def score_for_offset(offset_deg, rule='floor'):
    # offset is subtracted from computed longitudes to emulate slightly different ayanamsa
    matches = {}
    for name, deg in PLANETS.items():
        deg_adj = norm(deg - offset_deg)
        p = compute_pada_for_degree(deg_adj, rule=rule)
        exp = EXPECTED_PADAS.get(name)
        matches[name] = (deg, deg_adj, p, exp, p == exp)
    total_match = sum(1 for v in matches.values() if v[4])
    return total_match, matches

def find_best_offset(min_off=-0.5, max_off=0.5, step=0.01, rule='floor'):
    best = []
    best_score = -1
    off = min_off
    while off <= max_off + 1e-12:
        score, matches = score_for_offset(off, rule=rule)
        if score > best_score:
            best_score = score
            best = [(off, score, matches)]
        elif score == best_score:
            best.append((off, score, matches))
        off = round(off + step, 10)
    return best_score, best

if __name__ == "__main__":
    print("Searching best offset to align padas with printed chart...")
    # try both rules
    for rule in ('floor','upper'):
        best_score, best_list = find_best_offset(min_off=-0.5, max_off=0.5, step=0.01, rule='floor' if rule=='floor' else 'upper')
        print("\nRule:", rule, "→ best score:", best_score, "matches out of", len(EXPECTED_PADAS))
        # show top 3 candidates
        for off, score, matches in sorted(best_list, key=lambda x: abs(x[0]))[:5]:
            print(f"\n  Offset = {off:+.3f}°  → matches: {score}")
            for name, (orig, adj, pada, exp, ok) in matches.items():
                flag = "OK" if ok else "  "
                print(f"    {name:7s}: orig={orig:8.4f}° adj={adj:8.4f}° -> pada={pada}  expected={exp} {flag}")
    print("\nDone. If a good offset is found (e.g., many matches), apply that offset by subtracting it\nfrom the degrees before computing nakshatra/pada in your app (or tweak CHITRAPAKSHA_AYANAMSA_DEG).\n")
