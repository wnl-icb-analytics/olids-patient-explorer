"""
Referrals view page
"""

import streamlit as st
import pandas as pd
from services.record_service import get_patient_referrals
from utils.helpers import format_date, safe_str, format_practitioner_name


def render_referrals():
    """
    Render the referrals view page.
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

    st.markdown(f"## 📨 Referrals for Patient: {sk_patient_id}")

    with st.spinner("Loading referrals..."):
        referrals = get_patient_referrals(person_id)

    if referrals.empty:
        st.info("No referrals found")
        return

    st.markdown(f"**Showing {len(referrals):,} referral(s)**")

    display_df = referrals.copy()
    display_df['DATE_DISPLAY'] = display_df['CLINICAL_EFFECTIVE_DATE'].apply(format_date)
    display_df['REFERRAL'] = display_df['REFERRAL_DISPLAY'].apply(safe_str)
    display_df['PRIORITY'] = display_df['PRIORITY'].apply(
        lambda x: safe_str(x) if pd.notna(x) else ""
    )
    display_df['TYPE'] = display_df['REFERRAL_TYPE'].apply(
        lambda x: safe_str(x) if pd.notna(x) else ""
    )
    display_df['MODE'] = display_df['MODE'].apply(
        lambda x: safe_str(x) if pd.notna(x) else ""
    )
    display_df['DIRECTION'] = display_df['IS_OUTGOING_REFERRAL'].apply(
        lambda x: "Outgoing" if x == True else ("Incoming" if x == False else "")
    )
    display_df['PRACTITIONER'] = display_df.apply(
        lambda row: format_practitioner_name(
            row['PRACTITIONER_LAST_NAME'],
            row['PRACTITIONER_FIRST_NAME'],
            row['PRACTITIONER_TITLE']
        ),
        axis=1
    )

    display_df = display_df[[
        'DATE_DISPLAY',
        'REFERRAL',
        'PRIORITY',
        'TYPE',
        'MODE',
        'DIRECTION',
        'PRACTITIONER'
    ]]
    display_df.columns = ['Date', 'Referral', 'Priority', 'Type', 'Mode', 'Direction', 'Practitioner']

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=600 if len(display_df) > 10 else None
    )

    st.caption("Priority, type, mode and direction are only recorded for a subset of referrals in the source data")
