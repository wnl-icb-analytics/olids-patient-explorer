"""
Test requests (diagnostic orders) view page
"""

import streamlit as st
import pandas as pd
from services.record_service import get_patient_test_requests
from utils.helpers import format_date, safe_str, format_practitioner_name


def render_test_requests():
    """
    Render the test requests view page.
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

    st.markdown(f"## 🔬 Test Requests for Patient: {sk_patient_id}")

    with st.spinner("Loading test requests..."):
        test_requests = get_patient_test_requests(person_id)

    if test_requests.empty:
        st.info("No test requests found")
        # TODO: remove once the upstream person_id backfill for
        # DIAGNOSTIC_ORDER has landed
        st.caption(
            "⚠️ Test request data is not yet flowing into OLIDS (person linkage "
            "pending an upstream backfill) - absence here does not mean no tests "
            "were requested."
        )
        return

    st.markdown(f"**Showing {len(test_requests):,} test request(s)**")

    display_df = test_requests.copy()
    display_df['DATE_DISPLAY'] = display_df['CLINICAL_EFFECTIVE_DATE'].apply(format_date)
    display_df['TEST'] = display_df['TEST_DISPLAY'].apply(safe_str)
    display_df['RESULT'] = display_df['RESULT_DISPLAY'].apply(
        lambda x: safe_str(x) if pd.notna(x) else ""
    )
    display_df['RESULT_DATE_DISPLAY'] = display_df['RESULT_DATE'].apply(
        lambda x: format_date(x) if pd.notna(x) else ""
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

    display_df = display_df[[
        'DATE_DISPLAY',
        'TEST',
        'RESULT',
        'RESULT_DATE_DISPLAY',
        'PRACTITIONER'
    ]]
    display_df.columns = ['Date', 'Test', 'Result', 'Result Date', 'Practitioner']

    # Only pass height when constraining: height=None is rejected by
    # newer Streamlit versions
    height_kwargs = {"height": 600} if len(display_df) > 10 else {}
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        **height_kwargs
    )
