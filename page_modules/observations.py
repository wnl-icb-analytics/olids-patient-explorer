"""
Observations view page
"""

import streamlit as st
import pandas as pd
from services.record_service import get_patient_observations, calculate_date_range
from utils.helpers import format_date, format_value_with_unit, format_practitioner_name, safe_str
from config import DATE_RANGE_OPTIONS


def render_observations():
    """
    Render the observations view page.
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

    st.markdown(f"## 📊 Observations for Patient: {sk_patient_id}")

    # Filters
    st.markdown("### Filters")
    col1, col2 = st.columns([2, 3])

    with col1:
        date_range = st.selectbox(
            "Date Range",
            options=list(DATE_RANGE_OPTIONS.keys()),
            index=0
        )

    with col2:
        search_term = st.text_input(
            "Search by code or description",
            placeholder="e.g., '38341003' or 'blood pressure'",
            key="obs_search"
        )

    # Calculate date range
    date_from, date_to = calculate_date_range(date_range)

    # Load observations
    with st.spinner("Loading observations..."):
        observations = get_patient_observations(person_id, date_from, date_to, search_term)

    if observations.empty:
        st.info("No observations found for the selected filters")
    else:
        st.markdown(f"**Showing {len(observations):,} observations** (limited to 10,000 most recent)")

        # Prepare display dataframe
        display_df = observations.copy()
        display_df['CLINICAL_EFFECTIVE_DATE'] = display_df['CLINICAL_EFFECTIVE_DATE'].apply(format_date)

        # Combine result_value and result_text, preferring numeric value if present
        display_df['VALUE'] = display_df.apply(
            lambda row: format_value_with_unit(
                row['RESULT_VALUE'] if pd.notna(row['RESULT_VALUE']) else row['RESULT_TEXT'],
                row['RESULT_UNIT_DISPLAY']
            ),
            axis=1
        )

        # Format practitioner name
        display_df['PRACTITIONER'] = display_df.apply(
            lambda row: format_practitioner_name(
                row['PRACTITIONER_LAST_NAME'],
                row['PRACTITIONER_FIRST_NAME'],
                row['PRACTITIONER_TITLE'],
                row['PRACTITIONER_ROLE']
            ),
            axis=1
        )

        # Format is_problem as Yes/No
        display_df['IS_PROBLEM_DISPLAY'] = display_df['IS_PROBLEM'].apply(
            lambda x: "Yes" if x == True else "No"
        )

        # Mark confidential records
        display_df['OBSERVATION_DISPLAY'] = display_df.apply(
            lambda row: ("🔒 " if row['IS_CONFIDENTIAL'] else "") + safe_str(row['MAPPED_CONCEPT_DISPLAY']),
            axis=1
        )
        if display_df['IS_CONFIDENTIAL'].any():
            st.caption("🔒 marks records flagged confidential in the source system")


        # Format episodicity display
        display_df['EPISODICITY_DISPLAY'] = display_df['EPISODICITY_DISPLAY'].apply(
            lambda x: safe_str(x) if pd.notna(x) and x != "N/A" else ""
        )
        
        # Select and rename columns for display
        display_df = display_df[[
            'CLINICAL_EFFECTIVE_DATE',
            'MAPPED_CONCEPT_CODE',
            'OBSERVATION_DISPLAY',
            'VALUE',
            'IS_PROBLEM_DISPLAY',
            'EPISODICITY_DISPLAY',
            'PRACTITIONER'
        ]]
        display_df.columns = ['Date', 'Code', 'Observation', 'Value', 'Is Problem', 'Episodicity', 'Practitioner']

        # Display table
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=600
        )
