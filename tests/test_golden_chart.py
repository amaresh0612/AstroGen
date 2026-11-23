"""Golden snapshot of the fictional fixture chart.

Values were produced by the app-equivalent pipeline (tropical − Lahiri ayanamsa,
Placidus, LEGACY_KP_DASHA=False arithmetic). Any change here is a change in KP
output and must be deliberate.
"""
import pytest

GOLDEN_PLANETS = {
    "Sun": (331.1223, "Pisces", "Purva Bhadrapada", 4, "Jupiter", "Mars", 10),
    "Moon": (102.1231, "Cancer", "Pushya", 3, "Saturn", "Mars", 3),
    "Mars": (296.2787, "Capricorn", "Dhanishta", 1, "Mars", "Jupiter", 9),
    "Mercury": (347.3321, "Pisces", "Revati", 1, "Mercury", "Mercury", 11),
    "Jupiter": (133.9944, "Leo", "Purva Phalguni", 1, "Venus", "Venus", 4),
    "Venus": (307.7466, "Aquarius", "Shatabhisha", 1, "Rahu", "Rahu", 10),
    "Saturn": (290.6185, "Capricorn", "Shravana", 4, "Moon", "Venus", 9),
    "Rahu": (252.7467, "Sagittarius", "Mula", 4, "Ketu", "Mercury", 8),
    "Ketu": (72.7467, "Gemini", "Ardra", 2, "Rahu", "Mercury", 2),
}
GOLDEN_CUSPS = [41.6897, 67.848, 93.0343, 120.4862, 152.3037, 187.4549,
                221.6897, 247.848, 273.0343, 300.4862, 332.3037, 7.4549]
GOLDEN_CSL = {"1": "Mars", "2": "Rahu", "3": "Rahu", "4": "Ketu", "5": "Jupiter", "6": "Rahu",
              "7": "Moon", "8": "Jupiter", "9": "Saturn", "10": "Mercury", "11": "Rahu", "12": "Rahu"}
GOLDEN_SIGNIFICATORS = {
    "Sun": [4, 8, 10, 11], "Moon": [3, 9, 10], "Mars": [7, 9, 12], "Mercury": [2, 5, 11],
    "Jupiter": [1, 4, 6, 8, 10, 11], "Venus": [1, 4, 6, 8, 10, 11], "Saturn": [3, 9, 10],
    "Rahu": [1, 2, 4, 5, 6, 8, 10, 11], "Ketu": [2, 4, 5, 8, 11],
}
# Classical KP levels: 1 in star of occupant, 2 occupant, 3 in star of owner, 4 owner.
GOLDEN_LEVELS = {
    "Sun": {4: 1, 8: 3, 10: 2, 11: 3},
    "Jupiter": {1: 3, 4: 2, 6: 3, 8: 4, 10: 1, 11: 4},
    "Rahu": {1: 3, 2: 1, 4: 2, 5: 3, 6: 3, 8: 2, 10: 1, 11: 1},
    "Ketu": {2: 2, 4: 1, 5: 3, 8: 1, 11: 1},
}


@pytest.mark.parametrize("planet", list(GOLDEN_PLANETS))
def test_planet(natal, planet):
    lon, sign, nak, pada, star, sub, house = GOLDEN_PLANETS[planet]
    p = natal["planets"][planet]
    assert p["longitude"] == pytest.approx(lon, abs=1e-4)
    assert (p["sign"], p["nakshatra"], p["pada"], p["star_lord"], p["sub_lord"], p["house"]) == (
        sign, nak, pada, star, sub, house)


def test_cusps_and_csl(natal):
    cusps = [natal["houses"][str(h)]["cusp_degree"] for h in range(1, 13)]
    assert cusps == pytest.approx(GOLDEN_CUSPS, abs=1e-4)
    assert natal["cuspal_sublords"] == GOLDEN_CSL


def test_significators(natal):
    got = {p: sorted(s["signified_houses"]) for p, s in natal["significators"].items()}
    assert got == GOLDEN_SIGNIFICATORS
    for planet, levels in GOLDEN_LEVELS.items():
        stored = {int(h): i["level"] for h, i in natal["significator_matrix"][planet].items()}
        assert stored == levels, planet


def test_dasha_lock(natal):
    d = natal["dasha"]
    assert [(m["lord"], m["start"][:10]) for m in d["full_timeline"][:4]] == [
        ("Saturn", "1992-03-15"), ("Mercury", "1998-09-05"), ("Ketu", "2015-09-05"), ("Venus", "2022-09-05")]
    assert d["locked_md"] == {"lord": "Venus", "start": "2022-09-05", "end": "2042-09-05"}
    assert d["locked_ad"] == {"lord": "Sun", "start": "2026-01-04", "end": "2027-01-05"}
    assert d["locked_pd"] == {"lord": "Mercury", "start": "2026-08-24", "end": "2026-10-14"}
