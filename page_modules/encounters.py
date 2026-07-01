"""
Encounters view page - events of different types grouped inside their
encounters (OLIDS naming), mirroring the EMIS consultation journal.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from services.record_service import get_patient_encounters, get_patient_encounter_items
from utils.helpers import format_date, safe_str, format_practitioner_name
from config import ENCOUNTER_DATE_RANGE_OPTIONS, MAX_ENCOUNTER_GROUPS

ITEM_TYPE_ORDER = ["Observation", "Medication", "Referral", "Procedure request", "Test request"]


def render_encounters():
    """
    Render the encounters view: a scrollable journal of encounters, each
    a section containing the coded items recorded within it. Items
    without an encounter link are listed separately so nothing is hidden.
    """
    # Check if patient is selected
    if "selected_patient" not in st.session_state or not st.session_state.selected_patient:
        st.warning("No patient selected. Please search for a patient first.")
        if st.button("Back to Search"):
            st.session_state.page = "search"
            st.rerun()
        return

    sk_patient_id = st.session_state.selected_patient

    # Resolve person_id for record queries
    from services.patient_service import get_person_id
    person_id = get_person_id(sk_patient_id)
    if person_id is None:
        st.error("Failed to resolve patient identifier")
        return

    # Navigation buttons
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("← Back to Summary"):
            st.session_state.page = "patient_summary"
            st.rerun()
    with col2:
        if st.button("← Back to Search"):
            st.session_state.page = "search"
            st.session_state.search_results = None
            st.rerun()

    st.markdown(f"## 🗒️ Encounters for Patient: {sk_patient_id}")

    # Reset stale widget state from sessions started before an options change
    options = list(ENCOUNTER_DATE_RANGE_OPTIONS.keys())
    if st.session_state.get("encounter_date_range") not in options:
        st.session_state.pop("encounter_date_range", None)

    date_range = st.selectbox(
        "Date Range",
        options=options,
        index=0,
        key="encounter_date_range"
    )
    days = ENCOUNTER_DATE_RANGE_OPTIONS.get(date_range)
    date_from = (datetime.now().date() - timedelta(days=days)) if days else None

    with st.spinner("Loading encounters..."):
        encounters = get_patient_encounters(person_id, date_from)
        items = get_patient_encounter_items(person_id, date_from)

    if encounters.empty and items.empty:
        st.info("No encounters or clinical events found for the selected period")
        return

    # Split items into encounter-linked and unlinked
    linked = items[items['ENCOUNTER_ID'].notna()].copy()
    items_by_encounter = dict(tuple(linked.groupby('ENCOUNTER_ID'))) if not linked.empty else {}
    encounter_ids_with_items = set(items_by_encounter.keys())
    unlinked = items[
        items['ENCOUNTER_ID'].isna() |
        ~items['ENCOUNTER_ID'].isin(set(encounters['ID']) if not encounters.empty else set())
    ].copy()

    # Encounters that have coded items, most recent first
    if not encounters.empty:
        with_items = encounters[encounters['ID'].isin(encounter_ids_with_items)]
    else:
        with_items = pd.DataFrame()

    n_groups = len(with_items)
    st.markdown(f"**{n_groups:,} encounter(s) with coded items**")
    if n_groups > MAX_ENCOUNTER_GROUPS:
        st.caption(f"Showing the {MAX_ENCOUNTER_GROUPS} most recent - narrow the date range for older encounters")

    for _, enc in with_items.head(MAX_ENCOUNTER_GROUPS).iterrows():
        enc_items = items_by_encounter[enc['ID']]
        render_encounter_section(enc, enc_items)

    # Items not linked to any encounter shown, grouped flat by date
    if not unlinked.empty:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander(f"Items not linked to an encounter ({len(unlinked):,})"):
            display_df = prepare_items_table(unlinked, include_date=True)
            st.dataframe(display_df, use_container_width=True, hide_index=True, height=400)

    st.caption(
        "Groups events recorded against the same encounter. Not all events are "
        "linked to an encounter in the source data (medication issues in particular)."
    )


def render_encounter_section(enc, enc_items):
    """Render one encounter as a bordered section with its items table."""
    practitioner = format_practitioner_name(
        enc['PRACTITIONER_LAST_NAME'],
        enc['PRACTITIONER_FIRST_NAME'],
        enc['PRACTITIONER_TITLE'],
        enc['PRACTITIONER_ROLE']
    )

    # Source type labels are often migration placeholders - only show useful ones
    etype = enc['ENCOUNTER_TYPE']
    etype = safe_str(etype) if pd.notna(etype) and not str(etype).startswith('Awaiting') else None

    context_parts = []
    if etype:
        context_parts.append(etype)
    location = enc['LOCATION']
    if pd.notna(location) and safe_str(location) != "N/A" and safe_str(location) != etype:
        context_parts.append(safe_str(location))

    # Appointment context, present for appointment-backed encounters only.
    # Long values (e.g. NHS data dictionary attendance descriptions) are
    # trimmed for the caption; source can carry encoding artifacts.
    for col in ('SLOT_CATEGORY', 'CONTACT_MODE', 'APPOINTMENT_STATUS'):
        value = enc[col]
        if pd.notna(value) and safe_str(value) != "N/A":
            text = " ".join(safe_str(value).replace('�', ' ').split())
            if len(text) > 60:
                text = text[:57].rstrip() + "..."
            context_parts.append(text)

    context_parts.append(f"{len(enc_items)} item(s)")

    with st.container(border=True):
        st.markdown(f"**{format_date(enc['CLINICAL_EFFECTIVE_DATE'])} — {practitioner}**")
        st.caption(" · ".join(context_parts))
        # Item dates shown: requests are planned for future dates and
        # observations can be backdated, so they can differ from the
        # encounter date
        display_df = prepare_items_table(enc_items, include_date=True)
        st.dataframe(display_df, use_container_width=True, hide_index=True)


def prepare_items_table(items, include_date=False):
    """Prepare an items DataFrame for display."""
    df = items.copy()
    df['TYPE_SORT'] = df['ITEM_TYPE'].apply(
        lambda t: ITEM_TYPE_ORDER.index(t) if t in ITEM_TYPE_ORDER else 99
    )
    df = df.sort_values(['CLINICAL_EFFECTIVE_DATE', 'TYPE_SORT'], ascending=[False, True])

    df['ITEM'] = df.apply(
        lambda row: ("🔒 " if row['IS_CONFIDENTIAL'] == True else "") + safe_str(row['DETAIL']),
        axis=1
    )
    df['VALUE'] = df['DETAIL_VALUE'].apply(
        lambda x: safe_str(x) if pd.notna(x) else ""
    )

    if include_date:
        df['DATE'] = df['CLINICAL_EFFECTIVE_DATE'].apply(format_date)
        out = df[['DATE', 'ITEM_TYPE', 'ITEM', 'VALUE']]
        out.columns = ['Date', 'Type', 'Item', 'Value / Detail']
    else:
        out = df[['ITEM_TYPE', 'ITEM', 'VALUE']]
        out.columns = ['Type', 'Item', 'Value / Detail']
    return out
