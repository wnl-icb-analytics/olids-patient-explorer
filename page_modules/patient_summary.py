"""
Patient summary page - landing page when viewing a patient record
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from services.patient_service import get_patient_demographics, get_patient_registration_history, get_patient_ltc_summary
from services.record_service import get_record_summary
from utils.helpers import get_status_badge_html, format_date, format_boolean, safe_str, format_month_year


def render_patient_summary():
    """
    Render the patient summary page with demographics and navigation.

    Sections render top-down in cost order: the header needs only the
    single-row demographics lookup, so it paints before the heavier
    record-summary aggregate runs.
    """
    # Check if patient is selected
    if "selected_patient" not in st.session_state or not st.session_state.selected_patient:
        st.warning("No patient selected. Please search for a patient first.")
        if st.button("Back to Search"):
            st.session_state.page = "search"
            st.session_state.search_results = None
            st.rerun()
        return

    sk_patient_id = st.session_state.selected_patient

    # Back button
    if st.button("← Back to Search"):
        st.session_state.page = "search"
        st.session_state.search_results = None
        st.rerun()

    # Demographics: fast single-row lookup, paints the header immediately
    demographics = get_patient_demographics(sk_patient_id)

    if demographics.empty:
        st.error("Failed to load patient demographics")
        return

    patient = demographics.iloc[0]
    person_id = int(patient['PERSON_ID'])

    render_patient_header(patient)

    # Record summary: single combined aggregate query (the expensive bit)
    with st.spinner("Loading record summary..."):
        summary = get_record_summary(person_id)

    render_summary_metrics(summary)

    st.markdown("<br>", unsafe_allow_html=True)

    # Navigation buttons to different views
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📊 View Observations", use_container_width=True, type="primary"):
            st.session_state.page = "observations"
            st.rerun()

    with col2:
        if st.button("💊 View Medications", use_container_width=True, type="primary"):
            st.session_state.page = "medications"
            st.rerun()

    with col3:
        if st.button("📅 View Appointments", use_container_width=True, type="primary"):
            st.session_state.page = "appointments"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Demographics details in tabs
    tab1, tab2, tab3, tab4 = st.tabs(["👤 Core Demographics", "🏥 Registration", "📍 Geography", "🗣️ Language"])

    with tab1:
        render_core_demographics(patient)

    with tab2:
        render_registration_info(patient)
        st.markdown("<br>", unsafe_allow_html=True)
        render_registration_history(person_id)

    with tab3:
        render_geography_info(patient)

    with tab4:
        render_language_info(patient)

    st.markdown("<br>", unsafe_allow_html=True)

    # Long-term conditions summary
    render_ltc_summary(person_id)

    st.markdown("<br>", unsafe_allow_html=True)

    # Problems section (loaded on demand)
    render_problems_summary(person_id)


def render_patient_header(patient):
    """
    Render patient header with basic info.

    Args:
        patient: Patient demographics row
    """
    # Get badge HTML
    badge_html = get_status_badge_html(
        patient['IS_ACTIVE'],
        patient['IS_DECEASED'],
        patient.get('INACTIVE_REASON')
    )

    # Title with inline status badge
    st.markdown(f"## Patient Record: {patient['SK_PATIENT_ID']} {badge_html}", unsafe_allow_html=True)
    st.markdown(f"**Person ID:** {patient['PERSON_ID']}")


def render_summary_metrics(summary):
    """
    Render summary metrics.

    Args:
        summary: Record summary dictionary from get_record_summary
    """
    st.markdown("### Record Summary")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Observations", f"{summary['total_observations']:,}")

    with col2:
        st.metric("Medications (Current)", f"{summary['current_medications']:,}")
        st.caption(f"Total: {summary['total_medications']:,}")

    with col3:
        st.metric("Appointments (12m)", f"{summary['appointments_last_12m']:,}")
        st.caption(f"All time: {summary['total_appointments']:,}")

    with col4:
        most_recent = max(
            filter(pd.notna, [
                summary['obs_most_recent'],
                summary['med_most_recent'],
                summary['appt_most_recent'],
            ]),
            default=None
        )
        most_recent_str = format_date(most_recent) if most_recent is not None else "N/A"
        st.metric("Most Recent", most_recent_str)


def render_core_demographics(patient):
    """Render core demographics section."""
    # Row 1: Personal demographics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Age**")
        life_stage = safe_str(patient['AGE_LIFE_STAGE'])
        st.markdown(f"{safe_str(patient['AGE'])} years ({life_stage})")
        birth_date = format_month_year(patient['BIRTH_DATE_APPROX'])
        st.markdown(f"<small>Born: {birth_date}</small>", unsafe_allow_html=True)

    with col2:
        st.markdown("**Gender**")
        st.markdown(safe_str(patient['GENDER']))

    with col3:
        st.markdown("**Ethnicity**")
        st.markdown(safe_str(patient['ETHNICITY_SUBCATEGORY']))
        st.markdown(f"<small>{safe_str(patient['ETHNICITY_CATEGORY'])}</small>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Row 2: Practice and deceased status
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**GP Practice**")
        st.markdown(safe_str(patient['PRACTICE_NAME']))
        st.markdown(f"<small>Code: {safe_str(patient['PRACTICE_CODE'])}</small>", unsafe_allow_html=True)

    with col2:
        st.markdown("**PCN**")
        st.markdown(safe_str(patient['PCN_NAME']))

    with col3:
        st.markdown("**Deceased**")
        st.markdown(format_boolean(patient['IS_DECEASED']))
        if patient['IS_DECEASED'] and patient['DEATH_DATE_APPROX']:
            death_date = format_month_year(patient['DEATH_DATE_APPROX'])
            st.markdown(f"<small>Died: {death_date}</small>", unsafe_allow_html=True)

    # Row 3: School age (only if under 18)
    if patient['AGE'] < 18:
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**School Age**")
            primary = format_boolean(patient['IS_PRIMARY_SCHOOL_AGE'])
            secondary = format_boolean(patient['IS_SECONDARY_SCHOOL_AGE'])
            st.markdown(f"Primary: {primary}")
            st.markdown(f"Secondary: {secondary}")


def render_registration_info(patient):
    """Render registration information section."""
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Practice**")
        st.markdown(safe_str(patient['PRACTICE_NAME']))
        st.markdown(f"<small>Code: {safe_str(patient['PRACTICE_CODE'])}</small>", unsafe_allow_html=True)

        st.markdown("<br>**PCN**", unsafe_allow_html=True)
        st.markdown(safe_str(patient['PCN_NAME']))
        st.markdown(f"<small>Code: {safe_str(patient['PCN_CODE'])}</small>", unsafe_allow_html=True)

    with col2:
        st.markdown("**Registration Dates**")
        st.markdown(f"Start: {format_date(patient['REGISTRATION_START_DATE'])}")
        st.markdown(f"End: {format_date(patient['REGISTRATION_END_DATE'])}")

        st.markdown("<br>**ICB**", unsafe_allow_html=True)
        st.markdown(safe_str(patient['ICB_NAME']))
        st.markdown(f"<small>{safe_str(patient['BOROUGH_REGISTERED'])}</small>", unsafe_allow_html=True)


def render_geography_info(patient):
    """Render geography information section."""
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Resident Location**")
        st.markdown(f"Borough: {safe_str(patient['BOROUGH_RESIDENT'])}")
        st.markdown(f"ICB: {safe_str(patient['ICB_RESIDENT'])}")
        st.markdown(f"Local Authority: {safe_str(patient['LOCAL_AUTHORITY_NAME'])}")
        st.markdown(f"London Resident: {format_boolean(patient['IS_LONDON_RESIDENT'])}")

    with col2:
        st.markdown("**Area Classifications**")
        st.markdown(f"Neighbourhood: {safe_str(patient['NEIGHBOURHOOD_RESIDENT'])}")
        st.markdown(f"LSOA: {safe_str(patient['LSOA_NAME_21'])}")
        st.markdown(f"Ward: {safe_str(patient['WARD_NAME'])}")

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Deprivation (IMD 2019)**")
        st.markdown(f"Quintile: {safe_str(patient['IMD_QUINTILE_19'])}")
        st.markdown(f"Decile: {safe_str(patient['IMD_DECILE_19'])}")


def render_language_info(patient):
    """Render language information section."""
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Main Language**")
        st.markdown(safe_str(patient['MAIN_LANGUAGE']))
        st.markdown(f"<small>Type: {safe_str(patient['LANGUAGE_TYPE'])}</small>", unsafe_allow_html=True)

    with col2:
        st.markdown("**Interpreter**")
        st.markdown(f"Needed: {format_boolean(patient['INTERPRETER_NEEDED'])}")
        if patient['INTERPRETER_NEEDED']:
            st.markdown(f"Type: {safe_str(patient['INTERPRETER_TYPE'])}")


def render_registration_history(person_id):
    """
    Render registration history as a markdown list.

    Args:
        person_id: Person identifier
    """
    history = get_patient_registration_history(person_id)

    if history.empty:
        st.info("No registration history available")
        return

    total_periods = len(history)

    # Sort by period sequence descending (most recent first)
    history = history.sort_values('PERIOD_SEQUENCE', ascending=False)

    st.markdown("### Registration History")

    # Display as bullet points
    for idx, row in history.iterrows():
        effective_start = format_date(row['EFFECTIVE_START_DATE'])

        # Handle end date - check for NaT/None properly
        end_date = row['EFFECTIVE_END_DATE']
        if pd.isna(end_date) or end_date is None:
            effective_end = "Ongoing"
        else:
            effective_end = format_date(end_date)
            if effective_end == "N/A":
                effective_end = "Ongoing"

        practice_name = safe_str(row['PRACTICE_NAME'])
        practice_code = safe_str(row['PRACTICE_CODE'])

        # Build the bullet point text
        bullet_text = f"**Period {row['PERIOD_SEQUENCE']}**: "
        bullet_text += f"{effective_start} → {effective_end}"
        bullet_text += f" | {practice_name}"

        if practice_code and practice_code != "N/A":
            bullet_text += f" ({practice_code})"

        # Add current badge at the end if current
        if row['IS_CURRENT']:
            bullet_text += ' <span style="background-color: #28a745; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; font-weight: 600;">CURRENT</span>'

        st.markdown(f"- {bullet_text}", unsafe_allow_html=True)

    st.caption(f"Showing {total_periods} registration period(s)")
    st.markdown("<br>", unsafe_allow_html=True)

    # Detailed history in expandable section
    with st.expander("📜 View Detailed Registration History", expanded=False):
        for idx, row in history.iterrows():
            current_badge = " 🟢 **CURRENT**" if row['IS_CURRENT'] else ""
            active_status = "Active" if row['IS_ACTIVE'] else "Inactive"

            st.markdown(f"#### Period {row['PERIOD_SEQUENCE']}{current_badge}")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown(f"**Effective Dates**")
                st.markdown(f"Start: {format_date(row['EFFECTIVE_START_DATE'])}")
                st.markdown(f"End: {format_date(row['EFFECTIVE_END_DATE'])}")

                st.markdown(f"<br>**Registration**", unsafe_allow_html=True)
                st.markdown(f"Start: {format_date(row['REGISTRATION_START_DATE'])}")
                st.markdown(f"End: {format_date(row['REGISTRATION_END_DATE'])}")
                st.markdown(f"Status: {active_status}")

            with col2:
                st.markdown(f"**Practice**")
                st.markdown(f"{safe_str(row['PRACTICE_NAME'])}")
                st.markdown(f"<small>Code: {safe_str(row['PRACTICE_CODE'])}</small>", unsafe_allow_html=True)

                st.markdown(f"<br>**Location**", unsafe_allow_html=True)
                st.markdown(f"PCN: {safe_str(row['PCN_NAME'])}")
                st.markdown(f"Borough: {safe_str(row['BOROUGH_REGISTERED'])}")

            if idx < len(history) - 1:
                st.markdown("---")


def render_ltc_summary(person_id):
    """
    Render long-term conditions summary section.

    Args:
        person_id: Person identifier
    """
    ltc_data = get_patient_ltc_summary(person_id)

    if ltc_data.empty:
        return

    st.markdown("### 🏥 Long-Term Conditions")

    # Group by clinical domain
    domains = ltc_data['CLINICAL_DOMAIN'].unique()

    for domain in sorted(domains):
        domain_conditions = ltc_data[ltc_data['CLINICAL_DOMAIN'] == domain]

        st.markdown(f"**{domain}**")

        # Display conditions as badges
        badges_html = ""
        for _, condition in domain_conditions.iterrows():
            qof_class = "condition-qof" if condition['IS_QOF'] else "condition-other"
            qof_badge = ' <span style="background-color: #084298; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.75rem; margin-left: 4px;">QOF</span>' if condition['IS_QOF'] else ""
            earliest = format_date(condition['EARLIEST_DIAGNOSIS_DATE'])

            badges_html += f'<span class="condition-badge {qof_class}">{condition["CONDITION_NAME"]}{qof_badge}<br><small>Dx: {earliest}</small></span>'

        st.markdown(badges_html, unsafe_allow_html=True)
        st.markdown("")


def format_problem_display(row):
    """Problem name with a confidential marker where flagged."""
    prefix = "🔒 " if row.get('IS_CONFIDENTIAL') else ""
    return f"{prefix}{safe_str(row['MAPPED_CONCEPT_DISPLAY'])}"


def render_problems_table(problems):
    """Render a problems DataFrame as a display table."""
    from utils.helpers import format_practitioner_name

    display_df = problems.copy()
    display_df['DATE_DISPLAY'] = display_df['CLINICAL_EFFECTIVE_DATE'].apply(format_date)
    display_df['PROBLEM'] = display_df.apply(format_problem_display, axis=1)
    display_df['PRACTITIONER'] = display_df.apply(
        lambda row: format_practitioner_name(
            row['PRACTITIONER_LAST_NAME'],
            row['PRACTITIONER_FIRST_NAME'],
            row['PRACTITIONER_TITLE']
        ),
        axis=1
    )

    display_df = display_df[['DATE_DISPLAY', 'PROBLEM', 'PRACTITIONER']]
    display_df.columns = ['Date', 'Problem', 'Practitioner']

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=300
    )


def render_problems_summary(person_id):
    """
    Render problems summary section. Loaded on demand: expander bodies
    execute even when collapsed, so the query only runs once the user
    asks for it (cached thereafter).

    Args:
        person_id: Person identifier
    """
    from services.record_service import get_patient_problems

    with st.expander("🏥 Problems (Active & Past)", expanded=False):
        if st.session_state.get("problems_person") != person_id:
            if st.button("Load problems"):
                st.session_state.problems_person = person_id
                st.rerun()
            return

        with st.spinner("Loading problems..."):
            problems = get_patient_problems(person_id)

        if problems.empty:
            st.info("No problems found")
            return

        # Split into active and past problems based on problem_end_date
        # Current: problem_end_date is NULL or in the future
        # Past: problem_end_date is set and in the past
        now = datetime.now()

        active_problems = problems[
            (problems['PROBLEM_END_DATE'].isna()) |
            (pd.to_datetime(problems['PROBLEM_END_DATE']) > now)
        ].copy()

        past_problems = problems[
            (problems['PROBLEM_END_DATE'].notna()) &
            (pd.to_datetime(problems['PROBLEM_END_DATE']) <= now)
        ].copy()

        if problems['IS_CONFIDENTIAL'].any():
            st.caption("🔒 marks records flagged confidential in the source system")

        # Active Problems Section
        st.markdown("### Current Problems")
        if active_problems.empty:
            st.markdown("No current problems")
        else:
            st.markdown(f"**Showing {len(active_problems):,} current problem(s)**")
            render_problems_table(active_problems)

        st.markdown("<br>", unsafe_allow_html=True)

        # Past Problems Section
        st.markdown("### Past Problems")
        if past_problems.empty:
            st.markdown("No past problems")
        else:
            st.markdown(f"**Showing {len(past_problems):,} past problem(s)**")
            render_problems_table(past_problems)
