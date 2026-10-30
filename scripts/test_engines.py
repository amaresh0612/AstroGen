import warnings, logging, os, io, sys, types
from datetime import date

# Ensure repo root is on path
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

warnings.filterwarnings('ignore')
logging.disable(logging.CRITICAL)

st_stub = types.ModuleType('streamlit')
st_stub.session_state = {}
st_stub.secrets = {}
st_stub.cache_data = lambda f: f
st_stub.cache_resource = lambda f: f
sys.modules.setdefault('streamlit', st_stub)

from analysis.significator_strength import compute_significator_strength
from analysis.promise_denial import compute_all_topics
from analysis.long_term_transits import compute_long_term_transits
from analysis.almanac_builder import build_almanac
from reports.pdf.kp_packet_section import build_kp_packet_section
from reports.pdf.almanac_section import build_almanac_section
from schemas.event_houses import EVENT_HOUSES
from reportlab.platypus import SimpleDocTemplate, PageBreak
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch

planets = {
    'Sun':     {'house': 10, 'nakshatra': 'Uttara Ashadha', 'star_lord': 'Sun',  'sign': 'Capricorn', 'sign_lord': 'Saturn'},
    'Moon':    {'house': 4,  'nakshatra': 'Rohini',          'star_lord': 'Moon', 'sign': 'Taurus',    'sign_lord': 'Venus'},
    'Mars':    {'house': 6,  'nakshatra': 'Chitra',          'star_lord': 'Mars', 'sign': 'Virgo',     'sign_lord': 'Mercury'},
    'Mercury': {'house': 10, 'nakshatra': 'Shravana',        'star_lord': 'Moon', 'sign': 'Capricorn', 'sign_lord': 'Saturn'},
    'Jupiter': {'house': 2,  'nakshatra': 'Bharani',         'star_lord': 'Venus','sign': 'Taurus',    'sign_lord': 'Venus'},
    'Venus':   {'house': 11, 'nakshatra': 'Purva Bhadrapada','star_lord': 'Jupiter','sign':'Aquarius', 'sign_lord': 'Saturn'},
    'Saturn':  {'house': 1,  'nakshatra': 'Ashwini',         'star_lord': 'Ketu', 'sign': 'Aries',     'sign_lord': 'Mars'},
    'Rahu':    {'house': 8,  'nakshatra': 'Swati',           'star_lord': 'Rahu', 'sign': 'Libra',     'sign_lord': 'Venus'},
    'Ketu':    {'house': 2,  'nakshatra': 'Bharani',         'star_lord': 'Venus','sign': 'Taurus',    'sign_lord': 'Venus'},
}
houses = {str(i): {'sign': s, 'star_lord': ''} for i,s in enumerate([
    '','Aries','Taurus','Gemini','Cancer','Leo','Virgo',
    'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces'],1)}
cusps = {'1':'Saturn','2':'Venus','3':'Rahu','4':'Saturn','5':'Ketu','6':'Moon',
         '7':'Rahu','8':'Saturn','9':'Ketu','10':'Moon','11':'Rahu','12':'Saturn'}
natal_ref = {
    'birth': {'name':'Test User','date':'1985-04-01','time':'08:00:00','place':'Hyderabad, India','lat':17.385,'lng':78.4867,'tz':'Asia/Kolkata','ayanamsa':23.8765},
    'numerology': {'name_number': 3, 'life_path': 7},
    'planets': planets,
    'houses': houses,
    'cuspal_sublords': cusps,
    'dasha': {
        'locked_md': {'lord': 'Saturn', 'start': '2019-01-01', 'end': '2038-01-01'},
        'locked_ad': {'lord': 'Mercury', 'start': '2025-03-01', 'end': '2027-09-01'},
        'locked_pd': {'lord': 'Jupiter', 'start': '2026-04-01', 'end': '2026-11-01'},
        'full_timeline': []
    },
    'significators': {p: {'occupied_house': planets[p]['house'], 'owned_houses': [], 'signified_houses': [planets[p]['house']]} for p in planets}
}

print('Building strength map...')
sm = compute_significator_strength(planets, houses)
print('Building promise/denial...')
pd_list = compute_all_topics(planets, houses, cusps, sm, 'Saturn', 'Mercury', 'Jupiter')
print('Building long-term transits...')
lt = compute_long_term_transits(10.0, planets, from_date=date(2026,8,23), horizon_years=3, event_house_map=EVENT_HOUSES)
print('Building almanac 10 days...')
almanac_rows = build_almanac(natal_ref, from_date=date(2026,8,23), days=10)

print('Assembling PDF...')
kp_story = build_kp_packet_section(sm, pd_list, lt)
alm_story = build_almanac_section(almanac_rows)
full_story = kp_story + [PageBreak()] + alm_story

buf = io.BytesIO()
doc = SimpleDocTemplate(buf, pagesize=A4,
    leftMargin=0.5*inch, rightMargin=0.5*inch, topMargin=0.5*inch, bottomMargin=0.5*inch)
doc.build(full_story)
buf.seek(0)
with open('test_full_report.pdf','wb') as f:
    f.write(buf.read())
sz = os.path.getsize('test_full_report.pdf')
print('PDF written. Size:', sz, 'bytes (', round(sz/1024,1), 'KB)')

print()
print('=== Promise/Denial Results ===')
for p in pd_list:
    print(' ', p['topic_label'], '->', p['verdict'])

print()
print('=== Long-term Transits ===')
for t in lt[:5]:
    print(' ', t['planet'], t['ingress_date'], t['from_sign'],'->', t['to_sign'], 'H'+str(t['transit_house']))
