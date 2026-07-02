"""
Patient search page
"""

import streamlit as st
from services.patient_service import search_patient
from utils.helpers import render_status_badge, get_status_badge_html, safe_str, format_month_year


def render_search():
    """
    Render the patient search page.
    """
    st.title("OLIDS Patient Record Explorer")

    st.markdown("### Patient Search")

    # Initialize session state for search results
    if "search_results" not in st.session_state:
        st.session_state.search_results = None

    # Search container
    st.markdown('<div class="search-container">', unsafe_allow_html=True)
    st.markdown("Search for a patient by entering their **sk_patient_id** or **person_id**")

    # Use a form to enable ENTER key submission
    with st.form(key="search_form", clear_on_submit=False):
        # Search input
        search_term = st.text_input(
            "Patient Identifier",
            placeholder="Enter sk_patient_id or person_id",
            key="search_input",
            label_visibility="collapsed"
        )

        # Search button
        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            search_clicked = st.form_submit_button("Search", type="primary", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # Perform search
    if search_clicked and search_term:
        with st.spinner("Searching..."):
            results = search_patient(search_term)

            if results.empty:
                st.warning(f"No patient found with identifier: {search_term}")
                st.session_state.search_results = None
            else:
                # Store results in session state
                st.session_state.search_results = results

    elif search_clicked and not search_term:
        st.warning("Please enter a patient identifier to search")
        st.session_state.search_results = None

    # Display search results from session state
    if st.session_state.search_results is not None and not st.session_state.search_results.empty:
        st.markdown("---")
        st.markdown("### Search Results")

        for idx, row in st.session_state.search_results.iterrows():
            render_patient_card(row)

    # Display instructions
    if st.session_state.search_results is None:
        st.markdown("---")
        st.markdown("#### Instructions")
        st.markdown("""
        - Enter a **sk_patient_id** or **person_id**
        - Click **Search** to find the patient
        - Click **View Record** on a result to view the patient's complete record
        """)

    # Audit notice
    from config import AUDIT_FOOTER_HTML
    st.markdown(AUDIT_FOOTER_HTML, unsafe_allow_html=True)


def render_patient_card(patient_row):
    """
    Render a patient search result card.

    Args:
        patient_row: Pandas Series with patient data
    """
    with st.container():
        # Patient header
        col1, col2 = st.columns([3, 1])

        with col1:
            badge_html = get_status_badge_html(
                patient_row["IS_ACTIVE"],
                patient_row["IS_DECEASED"],
                patient_row.get("INACTIVE_REASON")
            )
            st.markdown(f"#### Patient: {patient_row['SK_PATIENT_ID']} {badge_html}", unsafe_allow_html=True)
            st.markdown(f"**Person ID:** {patient_row['PERSON_ID']}")

        with col2:
            # Empty column for spacing
            st.markdown("")

        # Demographics summary and button
        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            # Format age with DOB in brackets
            age = safe_str(patient_row["AGE"])
            dob = format_month_year(patient_row["BIRTH_DATE_APPROX"])
            st.metric("Age", f"{age} years ({dob})")

        with col2:
            st.metric("Gender", safe_str(patient_row["GENDER"]))

        with col3:
            # View record button - aligned with metrics
            st.markdown("<div style='padding-top: 18px;'>", unsafe_allow_html=True)
            if st.button("View Record", key=f"view_{patient_row['SK_PATIENT_ID']}", type="primary", use_container_width=True):
                st.session_state.page = "patient_summary"
                st.session_state.selected_patient = patient_row["SK_PATIENT_ID"]
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        # Practice info - more compact
        st.markdown(f"**Practice:** {safe_str(patient_row['PRACTICE_NAME'])} | **PCN:** {safe_str(patient_row['PCN_NAME'])}")

        st.markdown("---")
