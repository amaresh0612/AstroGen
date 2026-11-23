"""
Shared fixtures. All birth data here is FICTIONAL — never add real people.
"""
from __future__ import annotations

import ast
import math
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FICTIONAL_BIRTH = dict(
    name="Test Subject",
    dob=date(1992, 3, 15),
    tob=time(10, 30, 0),
    place="Hyderabad, India",
    lat=17.385,
    lng=78.4867,
    tz_name="Asia/Kolkata",
)
LOCK_DT = datetime(2026, 10, 1, 9, 0, 0)
HYDERABAD = dict(query_location="Hyderabad, India", query_lat=17.385, query_lng=78.4867,
                 query_tz="Asia/Kolkata")
LONDON = dict(query_location="London, UK", query_lat=51.5074, query_lng=-0.1278,
              query_tz="Europe/London")

APP_FUNCTIONS = (
    "get_sublord_kp_standard",
    "get_nakshatra_and_pada",
    "get_house_number_from_degree",
    "calculate_vimshottari_dasha",
    "compute_antardashas",
    "compute_pratyantardashas",
    "_legacy_days",
)


@pytest.fixture(scope="session")
def app_fns() -> dict:
    """
    The source-of-truth functions from app.py, extracted by AST so the
    Streamlit UI at module level never runs.
    """
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    ns: dict = {"math": math, "datetime": datetime, "timedelta": timedelta}
    wanted_assigns = {"NAKSHATRAS", "SIGNS", "LEGACY_KP_DASHA", "KP_MODE"}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in wanted_assigns for t in node.targets
        ):
            exec(compile(ast.Module([node], []), "app.py", "exec"), ns)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in APP_FUNCTIONS:
            exec(compile(ast.Module([node], []), "app.py", "exec"), ns)
    missing = [f for f in APP_FUNCTIONS if f not in ns]
    assert not missing, f"app.py functions not found: {missing}"
    return ns


@pytest.fixture(scope="session")
def natal() -> dict:
    from scripts.generate_natal_ref import build_natal_ref
    return build_natal_ref(**FICTIONAL_BIRTH, lock_dt=LOCK_DT)
