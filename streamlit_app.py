"""
OLIDS Patient Record Explorer
Main application entry point
"""

import streamlit as st
from config import PAGE_CONFIG, CUSTOM_CSS
from database import get_connection


def main():
    """
    Main application function.
    """
    # Page configuration
    st.set_page_config(**PAGE_CONFIG)

    # Apply custom CSS
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # Initialize database connection
    conn = get_connection()

    # Initialize session state
    if 'page' not in st.session_state:
        st.session_state.page = 'search'

    if 'selected_patient' not in st.session_state:
        st.session_state.selected_patient = None

    # Page routing
    if st.session_state.page == 'search':
        from page_modules.search import render_search
        render_search()
    elif st.session_state.page == 'patient_summary':
        from page_modules.patient_summary import render_patient_summary
        render_patient_summary()
    elif st.session_state.page == 'observations':
        from page_modules.observations import render_observations
        render_observations()
    elif st.session_state.page == 'medications':
        from page_modules.medications import render_medications
        render_medications()
    elif st.session_state.page == 'appointments':
        from page_modules.appointments import render_appointments
        render_appointments()
    elif st.session_state.page == 'referrals':
        from page_modules.referrals import render_referrals
        render_referrals()
    elif st.session_state.page == 'procedures':
        from page_modules.procedures import render_procedures
        render_procedures()
    elif st.session_state.page == 'consultations':
        from page_modules.consultations import render_consultations
        render_consultations()
    else:
        # Default to search page
        st.session_state.page = 'search'
        from page_modules.search import render_search
        render_search()


if __name__ == "__main__":
    main()
