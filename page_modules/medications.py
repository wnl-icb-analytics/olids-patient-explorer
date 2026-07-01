"""
Medications view page
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from services.record_service import get_patient_medications, calculate_date_range
from utils.helpers import format_date, safe_str, format_practitioner_name
from config import PAST_MEDICATIONS_DATE_RANGE_OPTIONS


def calculate_past_medications_date_range(range_option):
    """
    Calculate date range for past medications based on selection.

    Args:
        range_option: Selected date range option

    Returns:
        Tuple of (date_from, date_to) or (None, None) for all time
    """
    days = PAST_MEDICATIONS_DATE_RANGE_OPTIONS.get(range_option)

    if days is None:
        return None, None

    date_to = datetime.now().date()
    date_from = date_to - timedelta(days=days)

    return date_from, date_to


def calculate_medication_status(row):
    """
    Calculate medication status based on cancellation, expiry, and duration.

    Args:
        row: DataFrame row with medication data

    Returns:
        Status string: "Current", "Cancelled", "Expired", "Past", or "Unknown"
    """
    try:
        today = datetime.now()

        # Check if cancelled
        if not pd.isna(row['CANCELLATION_DATE']):
            cancellation_date = pd.to_datetime(row['CANCELLATION_DATE'])
            if cancellation_date <= today:
                return "Cancelled"

        # Check statement expiry date
        if not pd.isna(row['EXPIRY_DATE']):
            expiry_date = pd.to_datetime(row['EXPIRY_DATE'])
            if expiry_date < today:
                return "Expired"

        # Check statement is_active flag
        if not pd.isna(row['STATEMENT_IS_ACTIVE']) and row['STATEMENT_IS_ACTIVE'] == False:
            return "Past"

        # Check duration-based expiry
        if not pd.isna(row['CLINICAL_EFFECTIVE_DATE']) and not pd.isna(row['DURATION_DAYS']):
            start_date = pd.to_datetime(row['CLINICAL_EFFECTIVE_DATE'])
            duration_days = int(row['DURATION_DAYS'])
            end_date = start_date + timedelta(days=duration_days)

            if today <= end_date:
                return "Current"
            else:
                return "Expired"

        return "Current"
    except:
        return "Unknown"


def prepare_medications_display(medications):
    """
    Prepare medications dataframe for display.

    Args:
        medications: DataFrame with medication data

    Returns:
        Formatted DataFrame ready for display
    """
    if medications.empty:
        return pd.DataFrame()

    display_df = medications.copy()

    # Calculate medication status
    display_df['STATUS'] = display_df.apply(calculate_medication_status, axis=1)

    # Format date for display
    display_df['DATE_DISPLAY'] = display_df['CLINICAL_EFFECTIVE_DATE'].apply(format_date)

    # Format issue method (from medication_orders.issue_method_description)
    display_df['ISSUE_METHOD'] = display_df['ISSUE_METHOD_DESCRIPTION'].apply(safe_str)

    # Format authorisation type (from medication_statement.authorisation_type_display)
    display_df['AUTHORISATION_TYPE'] = display_df['AUTHORISATION_TYPE_DISPLAY'].apply(safe_str)

    # Format dose and quantity
    display_df['DOSE_INFO'] = display_df['DOSE'].apply(safe_str)
    display_df['QUANTITY_INFO'] = display_df.apply(
        lambda row: f"{safe_str(row['QUANTITY_VALUE'])} {safe_str(row['QUANTITY_UNIT'])}"
        if row['QUANTITY_VALUE'] and row['QUANTITY_UNIT'] else safe_str(row['QUANTITY_VALUE']),
        axis=1
    )

    # Format duration if available
    display_df['DURATION_INFO'] = display_df.apply(
        lambda row: f"{int(row['DURATION_DAYS'])} days"
        if row['DURATION_DAYS'] and str(row['DURATION_DAYS']) != 'nan' else "",
        axis=1
    )

    # Format practitioner name
    display_df['PRACTITIONER'] = display_df.apply(
        lambda row: format_practitioner_name(
            row['PRACTITIONER_LAST_NAME'],
            row['PRACTITIONER_FIRST_NAME'],
            row['PRACTITIONER_TITLE']
        ),
        axis=1
    )

    # Mark confidential records
    display_df['MEDICATION'] = display_df.apply(
        lambda row: ("🔒 " if row['IS_CONFIDENTIAL'] else "") + safe_str(row['MAPPED_CONCEPT_DISPLAY']),
        axis=1
    )

    # Select and rename columns for display
    display_df = display_df[[
        'DATE_DISPLAY',
        'STATUS',
        'ISSUE_METHOD',
        'AUTHORISATION_TYPE',
        'MEDICATION',
        'DOSE_INFO',
        'QUANTITY_INFO',
        'DURATION_INFO',
        'PRACTITIONER'
    ]]
    display_df.columns = [
        'Date', 'Status', 'Issue Method', 'Authorisation Type', 
        'Medication', 'Dose', 'Quantity', 'Duration', 'Prescriber'
    ]

    return display_df


def render_medications():
    """
    Render the medications view page.
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

    st.markdown(f"## 💊 Medications for Patient: {sk_patient_id}")

    # Search filter (applies to both Current and Past)
    search_term = st.text_input(
        "Search by code or description",
        placeholder="e.g., medication name or SNOMED code",
        key="med_search"
    )

    # Current Medications Section
    st.markdown("### Current Medications")
    
    with st.spinner("Loading current medications..."):
        current_medications = get_patient_medications(
            person_id, 
            date_from=None, 
            date_to=None, 
            search_term=search_term,
            current_only=True
        )

    if current_medications.empty:
        st.info("No current medications found")
    else:
        st.markdown(f"**Showing {len(current_medications):,} current medications**")
        current_display = prepare_medications_display(current_medications)
        st.dataframe(
            current_display,
            use_container_width=True,
            hide_index=True,
            height=300
        )

    # Past Medications Section
    st.markdown("### Past Medications")
    
    col1, col2 = st.columns([2, 3])
    with col1:
        date_range = st.selectbox(
            "Date Range",
            options=list(PAST_MEDICATIONS_DATE_RANGE_OPTIONS.keys()),
            index=0,  # Default to "90 days"
            key="past_med_date_range"
        )

    # Calculate date range for past medications
    date_from, date_to = calculate_past_medications_date_range(date_range)

    with st.spinner("Loading past medications..."):
        past_medications = get_patient_medications(
            person_id, 
            date_from=date_from, 
            date_to=date_to, 
            search_term=search_term,
            current_only=False
        )

        # Filter out current medications from past medications
        if not past_medications.empty:
            # Recalculate status to identify current vs past
            past_medications_copy = past_medications.copy()
            past_medications_copy['STATUS'] = past_medications_copy.apply(calculate_medication_status, axis=1)
            # Only show medications that are not current
            past_medications = past_medications[
                past_medications_copy['STATUS'].isin(['Cancelled', 'Expired', 'Past', 'Unknown'])
            ]

    if past_medications.empty:
        st.info("No past medications found for the selected filters")
    else:
        st.markdown(f"**Showing {len(past_medications):,} past medications** (limited to 10,000 most recent)")
        past_display = prepare_medications_display(past_medications)
        st.dataframe(
            past_display,
            use_container_width=True,
            hide_index=True,
            height=300
        )
