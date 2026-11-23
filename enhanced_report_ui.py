"""
KP Report UI — additive Streamlit module.

  1. Natal reference — session chart or uploaded JSON (locked source of truth)
  2. Prediction location — from birth-form current city (override optional)
  3. Unified Report PDF — auto-built once; single download (no AI narrative)
  4. AI Calculation Pack — separate ZIP: natal + 90-day pack + rules + longterm

Call render_enhanced_report_section() from app.py after the chart is computed.
"""
from __future__ import annotations

import io
import json
import zipfile
from datetime import date, datetime
from typing import Optional

import streamlit as st
from analysis.kp_constants import SIGN_LORDS, utc_now_iso
from schemas.event_houses import ALL_TOPICS


def _json_bytes(data: dict, compact: bool = False) -> bytes:
    def _serial(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        raise TypeError(f"Not serialisable: {type(obj)}")
    # The 90-day pack holds ~23k single-line RP interval arrays; indenting them
    # puts every element on its own line and inflates the file about 2.5x.
    layout = {"separators": (",", ":")} if compact else {"indent": 2}
    return json.dumps(data, ensure_ascii=False, default=_serial, **layout).encode("utf-8")


def _ai_pack_zip(
    natal_ref: dict,
    pack: dict,
    event_rules: dict,
    lt_transits: dict,
    natal_fn: str,
    pack_fn: str,
    rules_fn: str,
    lt_fn: str,
) -> bytes:
    """Bundle the four AI-ready JSON files into one ZIP (files stay separate inside)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(natal_fn, _json_bytes(natal_ref))
        zf.writestr(pack_fn, _json_bytes(pack, compact=True))
        zf.writestr(rules_fn, _json_bytes(event_rules))
        zf.writestr(lt_fn, _json_bytes(lt_transits))
    return buf.getvalue()


def _geocode_location(place: str) -> tuple[Optional[float], Optional[float], Optional[str]]:
    """Return (lat, lng, tz_name) for a place string, or (None, None, None) on failure."""
    if not place or not place.strip():
        return None, None, None
    try:
        from geopy.geocoders import Nominatim
        from timezonefinder import TimezoneFinder
        geolocator = Nominatim(user_agent="astrogen_ui")
        location = geolocator.geocode(place.strip(), timeout=10)
        if location is None:
            return None, None, None
        lat, lng = location.latitude, location.longitude
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lat=lat, lng=lng) or "Asia/Kolkata"
        return lat, lng, tz_name
    except Exception:
        return None, None, None


HOUSE_KEY_MAP = {
    "1st (Lagna)": "1", "2nd": "2", "3rd": "3",  "4th": "4",
    "5th": "5",         "6th": "6", "7th": "7",  "8th": "8",
    "9th": "9",         "10th": "10","11th": "11","12th": "12",
}
PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter",
           "Venus", "Saturn", "Rahu", "Ketu"]


def _chart_result_to_natal_ref(
    chart_result: dict,
    name: str,
    dob,
    tob,
    place: str,
    name_number: int = 0,
    life_path: int = 0,
) -> dict:
    """Convert app.py's chart_result dict into a natal_ref-compatible dict (in memory)."""
    location = chart_result.get("location", {})
    planets_raw = chart_result.get("planets", {})
    houses_raw = chart_result.get("houses", {})
    cuspal_map = chart_result.get("cuspal_sublords", {})
    dashas = chart_result.get("dashas", {})
    ayanamsa = float(chart_result.get("ayanamsa", 0))
    cusps_sid = chart_result.get("house_cusps_degrees", [])

    tob_str = tob.strftime("%H:%M:%S") if hasattr(tob, "strftime") else str(tob)

    _retro_flags: dict[str, bool] = {"Rahu": True, "Ketu": True}
    try:
        import swisseph as swe
        import pytz
        _PLANET_IDS = {
            "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
            "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
            "Venus": swe.VENUS, "Saturn": swe.SATURN,
        }
        _tz_name = location.get("tz_name", "Asia/Kolkata")
        _tz = pytz.timezone(_tz_name)
        if hasattr(dob, "year") and hasattr(tob, "hour"):
            _dt_local = _tz.localize(datetime(
                dob.year, dob.month, dob.day, tob.hour, tob.minute, tob.second,
            ))
            _dt_ut = _dt_local.astimezone(pytz.utc)
            _jd = swe.julday(
                _dt_ut.year, _dt_ut.month, _dt_ut.day,
                _dt_ut.hour + _dt_ut.minute / 60.0 + _dt_ut.second / 3600.0,
            )
            swe.set_sid_mode(swe.SIDM_LAHIRI)
            for _pname, _pid in _PLANET_IDS.items():
                _res = swe.calc_ut(_jd, _pid, swe.FLG_SWIEPH | swe.FLG_SPEED)
                _speed = _res[0][3] if isinstance(_res[0], (list, tuple)) else 0
                _retro_flags[_pname] = _speed < 0
    except Exception:
        pass

    planets_out: dict = {}
    for pname in PLANETS:
        p = planets_raw.get(pname, {})
        if not p:
            continue
        lon = float(p.get("full_degree", 0)) % 360.0
        sign = p.get("sign", "")
        planets_out[pname] = {
            "longitude": round(lon, 6),
            "sign": sign,
            "degree": p.get("degree", ""),
            "house": 0,
            "nakshatra": p.get("nakshatra", ""),
            "pada": int(p.get("pada", 0)),
            "star_lord": p.get("nakshatra_lord", ""),
            "sub_lord": p.get("sublord", ""),
            "sign_lord": SIGN_LORDS.get(sign, ""),
            "retrograde": _retro_flags.get(pname, False),
        }

    houses_out: dict = {}
    try:
        from analysis.panchanga import SIGNS as _SIGNS
    except Exception:
        _SIGNS = [
            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
        ]

    for hkey, hnum in HOUSE_KEY_MAP.items():
        h = houses_raw.get(hkey, {})
        idx = int(hnum) - 1
        lon = float(cusps_sid[idx]) if idx < len(cusps_sid) else 0.0
        if h:
            houses_out[hnum] = {
                "cusp_degree": round(float(h.get("cusp_degree", lon)), 6),
                "sign": h.get("sign", _SIGNS[int(lon / 30) % 12]),
                "degree": h.get("degree", ""),
                "nakshatra": h.get("nakshatra", ""),
                "star_lord": h.get("nakshatra_lord", ""),
                "sub_lord": cuspal_map.get(hnum, h.get("sublord", "")),
            }
        else:
            sign = _SIGNS[int(lon / 30) % 12]
            houses_out[hnum] = {
                "cusp_degree": round(lon, 6), "sign": sign,
                "degree": "", "nakshatra": "", "star_lord": "",
                "sub_lord": cuspal_map.get(hnum, ""),
            }

    cuspal_out = {str(i): cuspal_map.get(str(i), "") for i in range(1, 13)}

    from analysis.cuspal_houses import assign_cuspal_houses
    planets_out = assign_cuspal_houses(planets_out, houses_out, include_whole_sign=True)

    from analysis.significator_strength import (
        build_natal_significator_block,
        _serialize_strength_map,
        KP_METHODOLOGY,
    )
    sigs_out, strength_map = build_natal_significator_block(planets_out, houses_out)
    sig_matrix = _serialize_strength_map(strength_map)

    from analysis.vimshottari import lock_dasha
    dasha_section = lock_dasha(dashas.get("raw") or [], datetime.now())

    return {
        "_meta": {
            "source_report": "Generated from session chart (in-memory)",
            "generated_date": date.today().isoformat(),
            "version": "1.1",
        },
        "birth": {
            "name": name or "Unknown",
            "date": dob.isoformat() if hasattr(dob, "isoformat") else str(dob),
            "time": tob_str,
            "place": place or location.get("place", ""),
            "lat": round(float(location.get("lat", 0)), 6),
            "lng": round(float(location.get("lng", 0)), 6),
            "tz": location.get("tz_name", "Asia/Kolkata"),
            "ayanamsa": round(ayanamsa, 6),
        },
        "planets": planets_out,
        "houses": houses_out,
        "cuspal_sublords": cuspal_out,
        "significators": sigs_out,
        "significator_matrix": sig_matrix,
        "kp_methodology": KP_METHODOLOGY,
        "dasha": dasha_section,
        "numerology": {"name_number": name_number, "life_path": life_path},
    }


def _build_pdf(
    natal_ref: dict,
    query_date: date,
    qtime_str: str,
    almanac_days: int,
    topics: list[str],
    query_lat: Optional[float] = None,
    query_lng: Optional[float] = None,
    query_tz: Optional[str] = None,
    query_city: Optional[str] = None,
    chart_result: Optional[dict] = None,
    confirmed_milestones: Optional[list] = None,
    rp_trigger_windows: Optional[dict] = None,
) -> tuple[io.BytesIO, dict]:
    """Run all engines and return (unified pdf_buffer, prediction_context)."""
    from analysis.context import build_prediction_context
    from reports.pdf.rp_evidence_section import summarise_rp_triggers_for_pdf
    from reports.unified_pdf import build_unified_pdf

    # Optional client facts (e.g. confirmed promotion) — framing only, not chart math.
    if confirmed_milestones:
        natal_ref = {
            **natal_ref,
            "client_facts": {
                **(natal_ref.get("client_facts") or {}),
                "confirmed_milestones": list(confirmed_milestones),
            },
        }

    ctx = build_prediction_context(
        natal_ref,
        query_date,
        query_time_local=qtime_str,
        query_mode="LONG_TERM",
        topics=topics or None,
        query_location=query_city,
        query_lat=query_lat,
        query_lng=query_lng,
        query_tz=query_tz,
    )
    pack_rp = rp_trigger_windows or st.session_state.get("_enh_rp_triggers")
    if pack_rp:
        ctx = {**ctx, "rp_trigger_summary": summarise_rp_triggers_for_pdf(pack_rp)}
    buf = build_unified_pdf(
        natal_ref,
        ctx,
        chart_result=chart_result,
        almanac_days=almanac_days,
        topics=topics or None,
        query_lat=query_lat,
        query_lng=query_lng,
        query_tz=query_tz,
        query_city=query_city,
        confirmed_milestones=list(confirmed_milestones or []),
        rp_trigger_windows=pack_rp,
    )
    return buf, ctx


def _show_pdf_download(ctx: dict, buf: io.BytesIO, filename: str, dl_key: str = "dl_pdf") -> None:
    """Show ruling planets summary and the single Report PDF download."""
    st.success("Report PDF ready")

    rp = ctx.get("ruling_planets", {})
    if rp.get("rp_list"):
        st.markdown(
            f"**Ruling Planets** *(at {rp.get('reference_time', '')})*: "
            f"{', '.join(rp['rp_list'])}"
        )

    st.download_button(
        label="📥 Download KP Calculation & Evidence Report (PDF)",
        data=buf.getvalue(),
        file_name=filename,
        mime="application/pdf",
        key=dl_key,
        type="primary",
    )


def _build_session_natal_ref(
    chart_result: dict,
    name: str,
    dob,
    tob,
    place: str,
    numerology: Optional[dict],
) -> dict:
    num = numerology or {}
    return _chart_result_to_natal_ref(
        chart_result, name, dob, tob, place,
        int(num.get("name_number", 0)),
        int(num.get("life_path", 0)),
    )


def _resolve_natal_ref(
    chart_result: dict,
    name: str,
    dob,
    tob,
    place: str,
    numerology: Optional[dict],
    uploaded_bytes: Optional[bytes],
) -> tuple[Optional[dict], str, Optional[str]]:
    """
    Return (natal_ref, source_label, parse_error).
    Uploaded JSON takes precedence over the session chart.
    """
    if uploaded_bytes:
        try:
            natal_ref = json.loads(uploaded_bytes)
            birth = natal_ref.get("birth", {})
            label = (
                f"Uploaded JSON — {birth.get('name', 'Unknown')} · "
                f"{birth.get('date', '')} · {birth.get('place', '')}"
            )
            return natal_ref, label, None
        except Exception as exc:
            return None, "", str(exc)

    if not chart_result:
        return None, "", "Compute a chart above first, or upload a saved natal JSON."

    natal_ref = _build_session_natal_ref(chart_result, name, dob, tob, place, numerology)
    birth = natal_ref.get("birth", {})
    label = (
        f"Session chart — {birth.get('name', 'Unknown')} · "
        f"{birth.get('date', '')} · {birth.get('place', '')}"
    )
    return natal_ref, label, None


def _render_natal_download(natal_ref: dict, key: str) -> None:
    birth = natal_ref.get("birth", {})
    safe = (birth.get("name") or "Chart").replace(" ", "_")
    birth_date_str = birth.get("date", "")
    dasha = natal_ref.get("dasha", {})
    md, ad, pd = dasha.get("locked_md", {}), dasha.get("locked_ad", {}), dasha.get("locked_pd", {})
    if md.get("lord"):
        st.success(
            f"MD: **{md['lord']}** ({md.get('start', '')} → {md.get('end', '')})  |  "
            f"AD: **{ad.get('lord', '—')}** ({ad.get('start', '')} → {ad.get('end', '')})  |  "
            f"PD: **{pd.get('lord', '—')}** ({pd.get('start', '')} → {pd.get('end', '')})"
        )
    with st.expander("Optional: save natal JSON only", expanded=False):
        st.caption(
            "Usually you only need the AI Calculation Pack ZIP in section 4 "
            "(it already includes this natal file). Use this if you want a natal backup alone."
        )
        st.download_button(
            label="💾 Download natal reference JSON",
            data=_json_bytes(natal_ref),
            file_name=f"natal_ref_{safe}_{birth_date_str}.json",
            mime="application/json",
            key=key,
        )


def _pdf_config_widgets(key_prefix: str) -> tuple:
    c1, c2 = st.columns(2)
    with c1:
        q_date = st.date_input(
            "Reference date", value=date.today(), key=f"{key_prefix}_date",
            help="Date for Panchanga, Hora and Ruling Planets",
        )
        q_time = st.text_input(
            "Reference time (HH:MM, 24h)", value="09:00", key=f"{key_prefix}_time",
            help="Use your current local time for Ruling Planets",
        )
    with c2:
        st.caption(
            f"Almanac: fixed **90 days**. Activation score card includes all "
            f"{len(ALL_TOPICS)} topics (career, marriage, wealth, travel, …)."
        )
    return q_date, q_time, 90


def _resolve_prediction_location(prediction_location: str) -> str:
    """Birth-form location wins when freshly set; otherwise keep the override widget."""
    from_form = (prediction_location or st.session_state.get("prediction_location", "")).strip()
    if from_form and st.session_state.get("_pred_loc_synced") != from_form:
        st.session_state["_pred_loc_synced"] = from_form
        st.session_state["enh_pred_loc"] = from_form
    if "enh_pred_loc" not in st.session_state:
        st.session_state["enh_pred_loc"] = from_form
    return (st.session_state.get("enh_pred_loc") or from_form or "").strip()


def _geocode_cached(place: str) -> tuple[Optional[float], Optional[float], Optional[str]]:
    cache = st.session_state.setdefault("_enh_geocode_cache", {})
    key = place.strip().lower()
    if key in cache:
        return cache[key]
    result = _geocode_location(place)
    if result[0] is not None:
        cache[key] = result
    return result


def render_enhanced_report_section(
    chart_result: dict,
    name: str,
    dob,
    tob,
    place: str,
    numerology: Optional[dict] = None,
    prediction_location: str = "",
) -> None:
    """
    Render the KP Report section: one auto-built PDF + optional AI pack ZIP.
    Prediction location comes from the birth form on first generate.
    """
    st.markdown("---")
    st.markdown("### ✦ KP Report")
    st.caption(
        "One Calculation & Evidence PDF builds automatically from your current city. "
        "AI Calculation Pack ZIP is a separate optional download."
    )

    st.markdown("#### 1 · Natal reference")
    st.caption(
        "Use the chart computed above, or upload a previously saved `natal_ref.json`. "
        "Everything below reads from this single locked chart."
    )

    uploaded = st.file_uploader(
        "Upload saved natal JSON (optional — overrides session chart)",
        type=["json"],
        key="enh_natal_upload",
        help="Returning users: upload your downloaded natal file to skip re-entering birth details.",
    )
    uploaded_bytes = uploaded.read() if uploaded else None

    natal_ref, natal_label, natal_err = _resolve_natal_ref(
        chart_result, name, dob, tob, place, numerology, uploaded_bytes,
    )
    if natal_err:
        st.error(natal_err)
        return

    st.info(natal_label)
    _render_natal_download(natal_ref, key="enh_natal_download")

    from analysis.significator_strength import KP_METHODOLOGY, significators_are_current
    if not significators_are_current(natal_ref):
        st.warning(
            "This natal file's significators predate method "
            f"{KP_METHODOLOGY['version']} (classical KP levels + Rahu/Ketu agency). "
            "Reports recompute them in memory, but the file itself still holds the old ones — "
            "re-download the natal JSON from a session chart before giving it to the AI."
        )
    if not (natal_ref.get("dasha") or {}).get("locked_periods"):
        st.warning(
            "This natal file has no locked AD/PD table (`locked_periods`). "
            "AD/PD will be derived from the mahadasha timeline and flagged as such. "
            "Re-download the natal JSON from a session chart to lock them."
        )

    from analysis.cuspal_houses import validate_cuspal_occupancy
    occ_issues = validate_cuspal_occupancy(
        natal_ref.get("planets", {}),
        natal_ref.get("houses", {}),
    )
    if occ_issues:
        st.error(
            "**Cuspal occupancy mismatch** — planet houses do not match cusp boundaries. "
            "Re-download natal JSON (do not use whole-sign occupancy). "
            f"Example: {occ_issues[0]}"
        )

    birth = natal_ref.get("birth", {})
    safe_name = (birth.get("name") or name or "Chart").replace(" ", "_")

    st.markdown("#### 2 · Prediction location")
    st.caption(
        "Taken from **Current city** on the birth form. Birth place is never used here."
    )
    q_location = _resolve_prediction_location(prediction_location)
    with st.expander("Change prediction location", expanded=not bool(q_location)):
        st.text_input(
            "Current city (city, country)",
            key="enh_pred_loc",
            placeholder="e.g. Hyderabad, India",
            help=(
                "All dynamic calculations use THIS location. "
                "Natal/birth location is stored only in natal JSON."
            ),
        )
        q_location = (st.session_state.get("enh_pred_loc") or "").strip()
    if q_location:
        st.info(f"Prediction location: **{q_location}**")
        st.session_state["prediction_location"] = q_location
    else:
        st.warning(
            "Enter **Current city (prediction location)** on the birth form "
            "and click Generate Complete KP Chart."
        )

    st.markdown("---")

    st.markdown("#### 3 · Report PDF")
    st.caption(
        "Single Calculation & Evidence Report — built automatically once the chart "
        "and prediction location are set. No AI predictions in the PDF."
    )
    q_date, q_time, alm_days = _pdf_config_widgets("enh_pdf")
    promo_confirmed = st.checkbox(
        "Promotion already announced / effective (post-promotion assessment)",
        value="promotion_announced" in (
            (st.session_state.get("confirmed_milestones") or [])
        ),
        key="enh_promo_confirmed",
        help=(
            "When checked, the Report PDF treats promotion as confirmed and lists "
            "implementation / authority / pay / team themes — never as a pending event."
        ),
    )
    milestones = ["promotion_announced", "promotion_effective"] if promo_confirmed else []
    st.session_state["confirmed_milestones"] = milestones
    force_rebuild = st.button("Rebuild PDF", key="enh_pdf_rebuild")

    if q_location:
        time_parts = (q_time or "09:00").split(":")
        try:
            qtime_str = f"{int(time_parts[0]):02d}:{int(time_parts[1]):02d}:00"
        except (ValueError, IndexError):
            qtime_str = "09:00:00"
            st.warning("Invalid reference time — using 09:00.")

        pdf_fingerprint = (
            f"{safe_name}|{birth.get('date','')}|{q_location}|{q_date}|{qtime_str}|"
            f"{alm_days}|{','.join(milestones)}"
        )
        needs_build = (
            force_rebuild
            or st.session_state.get("_enh_pdf_key") != pdf_fingerprint
            or not st.session_state.get("_enh_buf")
        )

        if needs_build:
            qlat, qlng, qtz = _geocode_cached(q_location)
            if qlat is None:
                st.error(
                    f"Could not geocode '{q_location}'. "
                    "Enter a valid city (e.g. 'Hyderabad, India')."
                )
            else:
                try:
                    with st.spinner(
                        f"Building Report PDF + {alm_days}-day almanac for {q_location}…"
                    ):
                        buf, ctx = _build_pdf(
                            natal_ref, q_date, qtime_str, alm_days, list(ALL_TOPICS),
                            query_lat=qlat, query_lng=qlng, query_tz=qtz,
                            query_city=q_location,
                            chart_result=chart_result,
                            confirmed_milestones=milestones,
                            rp_trigger_windows=st.session_state.get("_enh_rp_triggers"),
                        )
                    st.session_state["_enh_buf"] = buf.getvalue()
                    st.session_state["_enh_ctx"] = ctx
                    st.session_state["_enh_fn"] = f"KP_Report_{safe_name}_{q_date}.pdf"
                    st.session_state["_enh_gen_at"] = utc_now_iso()
                    st.session_state["_enh_pdf_key"] = pdf_fingerprint
                except Exception as e:
                    st.error(f"Failed: {e}")
                    import traceback
                    st.code(traceback.format_exc())

    if st.session_state.get("_enh_buf") and q_location:
        gen_at = st.session_state.get("_enh_gen_at", "")
        if gen_at:
            st.caption(f"PDF generated at **{gen_at} UTC**.")
        _show_pdf_download(
            st.session_state["_enh_ctx"],
            io.BytesIO(st.session_state["_enh_buf"]),
            st.session_state["_enh_fn"],
            dl_key="enh_pdf_dl",
        )
    elif not q_location:
        st.info("Report PDF will appear here after you set the current city.")

    st.markdown("---")

    st.markdown("#### 4 · AI Calculation Pack (ZIP)")
    st.caption(
        "Optional separate download for your AI project: natal lock + 90-day daily "
        "calculations + `kp_rules.json` + long-term transits."
    )

    with st.form("enh_pack_form"):
        col1, col2 = st.columns(2)
        with col1:
            pack_start = st.date_input("Start date", value=date.today(), key="enh_pack_start")
        with col2:
            pack_ref_time = st.text_input(
                "Transit snapshot time (HH:MM local)",
                value="09:00", key="enh_pack_reftime",
                help=("Daily transit positions and the daily Ruling Planet snapshot use "
                      "this local time. Full RP intervals for every day are stored "
                      "regardless, so any exact time can be looked up later."),
            )
        pack_loc = st.text_input(
            "Prediction location (defaults to current city if blank)",
            value="", key="enh_pack_loc",
            placeholder="Leave blank to use current city from birth form",
        )
        pack_submitted = st.form_submit_button(
            "Generate AI Calculation Pack 📦", type="primary",
        )

    if pack_submitted:
        effective_loc = (pack_loc or q_location or "").strip()
        if not effective_loc:
            st.error("Prediction location is required (birth form current city or pack form).")
        else:
            qlat, qlng, qtz = _geocode_cached(effective_loc)
            if qlat is None:
                st.error(
                    f"Could not geocode '{effective_loc}'. "
                    "Enter a valid city name."
                )
            else:
                progress_bar = st.progress(0, text="Initialising…")
                status_text = st.empty()
                total = 90

                def _on_progress(idx: int, day_val) -> None:
                    pct = int((idx + 1) / total * 100)
                    progress_bar.progress(pct, text=f"Day {idx + 1}/{total}: {day_val}")
                    status_text.markdown(f"Computing **{day_val}** ({idx + 1}/{total})…")

                try:
                    from analysis.pack_builder import build_90day_pack
                    from analysis.reference_exports import (
                        build_kp_rules,
                        build_longterm_transits,
                        longterm_transits_filename,
                    )
                    pack = build_90day_pack(
                        natal_ref=natal_ref,
                        start_date=pack_start,
                        num_days=total,
                        prediction_city=effective_loc,
                        prediction_lat=qlat,
                        prediction_lng=qlng,
                        prediction_tz=qtz,
                        reference_time=pack_ref_time or "09:00",
                        on_progress=_on_progress,
                    )
                    event_rules = build_kp_rules()
                    lt_transits = build_longterm_transits(
                        natal_ref, pack_start, horizon_years=5,
                    )
                    loc_slug = effective_loc.split(",")[0].strip().replace(" ", "_")
                    pack_fn = f"{safe_name}_90day_pack_{loc_slug}_{pack_start.isoformat()}.json"
                    rules_fn = "kp_rules.json"
                    lt_fn = longterm_transits_filename(pack_start, horizon_years=5)
                    natal_fn = pack.get("natal_reference_file", f"natal_ref_{safe_name}.json")
                    zip_bytes = _ai_pack_zip(
                        natal_ref, pack, event_rules, lt_transits,
                        natal_fn, pack_fn, rules_fn, lt_fn,
                    )
                    zip_fn = f"{safe_name}_AI_pack_{loc_slug}_{pack_start.isoformat()}.zip"
                    st.session_state["_enh_ai_pack"] = {
                        "zip_bytes": zip_bytes,
                        "zip_fn": zip_fn,
                        "pack": pack,
                        "location": effective_loc,
                        "files": [natal_fn, pack_fn, rules_fn, lt_fn],
                        "gen_at": utc_now_iso(),
                    }
                    # Attach timed-RP summary so Rebuild PDF can show section B.
                    st.session_state["_enh_rp_triggers"] = pack.get("rp_trigger_windows")
                    st.session_state["_enh_pdf_key"] = None  # force PDF rebuild with pack data
                except Exception as e:
                    import traceback
                    st.error(f"Pack generation failed: {e}")
                    st.code(traceback.format_exc())
                    st.stop()

                progress_bar.progress(100, text="Done!")
                status_text.empty()

    ai_pack = st.session_state.get("_enh_ai_pack")
    if ai_pack:
        pack = ai_pack["pack"]
        val = pack.get("validation", {})
        trust = val.get("trust_status", {})
        for w in val.get("warnings", []):
            st.warning(w)
        if val.get("overall") == "PASS":
            st.success(
                f"✅ All validation layers passed — {pack['num_days']} days ready in one ZIP."
            )
        else:
            st.error(f"⛔ Validation **{val.get('overall', 'FAIL')}** — review before using.")
            if trust:
                cols = st.columns(4)
                for i, (layer, status) in enumerate(trust.items()):
                    cols[i % 4].markdown(
                        f"**{layer}**: {'✅' if status == 'PASS' else '❌'} {status}"
                    )
            if val.get("issues"):
                st.warning(
                    "Issues found:\n"
                    + "\n".join(f"• {iss}" for iss in val.get("issues", [])[:10])
                )

        m1, m2, m3 = st.columns(3)
        m1.metric("Days", pack["num_days"])
        m2.metric("Location", ai_pack["location"].split(",")[0])
        m3.metric("MD", pack["natal_lock"].get("md_lord", "—"))
        st.caption(
            f"Valid: **{pack['valid_from']}** → **{pack['valid_to']}** · "
            f"Generated: {ai_pack['gen_at']} UTC · "
            f"Engine: {pack['calculation_engine']}"
        )
        st.download_button(
            label=f"📥 Download AI Calculation Pack ZIP ({len(ai_pack['zip_bytes']) / 1024 / 1024:.1f} MB)",
            data=ai_pack["zip_bytes"],
            file_name=ai_pack["zip_fn"],
            mime="application/zip",
            key="enh_ai_pack_zip_dl",
            type="primary",
        )
        st.info(
            "Unzip and upload these four files to your AI project:\n"
            + "\n".join(f"- `{fn}`" for fn in ai_pack["files"])
            + f"\n\nThe 90-day pack covers **{pack['valid_from']} → {pack['valid_to']}**. "
            "Generate a new pack before that end date so questions stay inside coverage."
        )
