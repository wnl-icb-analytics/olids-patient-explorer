"""
Results view page - numeric observation results with a history chart
and value list per result type, like the EMIS test results screen.
"""

import streamlit as st
import pandas as pd
import altair as alt
from services.record_service import get_patient_result_types, get_patient_result_series
from utils.helpers import format_date, safe_str, format_practitioner_name


def render_results():
    """
    Render the results view: pick a numeric result type, see the
    historic values as a chart and a list.
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

    st.markdown(f"## 🧪 Results for Patient: {sk_patient_id}")

    with st.spinner("Loading result types..."):
        result_types = get_patient_result_types(person_id)

    if result_types.empty:
        st.info("No numeric results recorded for this patient")
        return

    labels = {
        row['RESULT_DISPLAY']: (
            f"{row['RESULT_DISPLAY']} ({row['RESULT_COUNT']:,}) · last {format_date(row['LATEST_DATE'])}"
        )
        for _, row in result_types.iterrows()
    }

    selected = st.selectbox(
        f"Result type ({len(result_types):,} recorded)",
        options=list(labels.keys()),
        format_func=lambda k: labels[k],
        key="result_type_select"
    )

    if not selected:
        return

    with st.spinner("Loading result history..."):
        series = get_patient_result_series(person_id, selected)

    if series.empty:
        st.info("No values found for this result")
        return

    units = series['RESULT_UNIT_DISPLAY'].dropna().unique()
    unit_label = safe_str(units[0]) if len(units) == 1 else "Value"

    st.markdown(f"### {selected}")

    # History chart (oldest to newest)
    chart_df = series.copy()
    chart_df['CLINICAL_EFFECTIVE_DATE'] = pd.to_datetime(chart_df['CLINICAL_EFFECTIVE_DATE'])
    chart = alt.Chart(chart_df).mark_line(point=True).encode(
        x=alt.X('CLINICAL_EFFECTIVE_DATE:T', title='Date'),
        y=alt.Y('RESULT_VALUE:Q', title=unit_label, scale=alt.Scale(zero=False)),
        tooltip=[
            alt.Tooltip('CLINICAL_EFFECTIVE_DATE:T', title='Date', format='%d %b %Y'),
            alt.Tooltip('RESULT_VALUE:Q', title='Value'),
            alt.Tooltip('RESULT_UNIT_DISPLAY:N', title='Unit'),
        ]
    ).properties(width="container", height=320)
    st.altair_chart(chart, use_container_width=True)

    if len(units) > 1:
        st.caption(f"⚠️ Multiple units recorded for this result: {', '.join(safe_str(u) for u in units)}")

    # Value list, most recent first
    st.markdown(f"**{len(series):,} value(s)**")

    display_df = series.copy()
    display_df['DATE_DISPLAY'] = display_df['CLINICAL_EFFECTIVE_DATE'].apply(format_date)
    display_df['VALUE'] = display_df.apply(
        lambda row: ("🔒 " if row['IS_CONFIDENTIAL'] == True else "") + safe_str(row['RESULT_VALUE']),
        axis=1
    )
    display_df['UNIT'] = display_df['RESULT_UNIT_DISPLAY'].apply(
        lambda x: safe_str(x) if pd.notna(x) else ""
    )
    display_df['PRACTITIONER'] = display_df.apply(
        lambda row: format_practitioner_name(
            row['PRACTITIONER_LAST_NAME'],
            row['PRACTITIONER_FIRST_NAME'],
            row['PRACTITIONER_TITLE'],
            row['PRACTITIONER_ROLE']
        ),
        axis=1
    )

    display_df = display_df[['DATE_DISPLAY', 'VALUE', 'UNIT', 'PRACTITIONER']]
    display_df.columns = ['Date', 'Value', 'Unit', 'Recorded By']

    # Only pass height when constraining: height=None is rejected by
    # newer Streamlit versions
    height_kwargs = {"height": 400} if len(display_df) > 10 else {}
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        **height_kwargs
    )
