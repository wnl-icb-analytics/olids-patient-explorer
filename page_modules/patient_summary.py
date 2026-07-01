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

    # Banner includes the allergy status line (safety-critical, always visible)
    render_patient_header(patient, person_id)

    # Record summary: single combined aggregate query (the expensive bit);
    # counts render on the navigation cards
    with st.spinner("Loading record summary..."):
        summary = get_record_summary(person_id)

    render_navigation(summary)

    st.markdown("<br>", unsafe_allow_html=True)

    # Long-term conditions summary
    render_ltc_summary(person_id)

    st.markdown("<br>", unsafe_allow_html=True)

    # Health status & prevention (single-trip query over reporting marts;
    # returns the problems tab slot for deferred filling below)
    problems_slot = render_health_status(person_id)

    st.markdown("<br>", unsafe_allow_html=True)

    # Demographic & registration detail last (clinical content first)
    st.markdown("#### Patient Details")
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

    # Deferred: the problems query runs after the whole page has painted
    # and fills its tab in place. Tab switches are client-side, so the
    # content must be rendered within this same run.
    if problems_slot is not None:
        with problems_slot:
            render_problems_tab(person_id)


def render_patient_header(patient, person_id):
    """
    Render a dense EPR-style patient banner with the allergy status line.

    Args:
        patient: Patient demographics row
        person_id: Person identifier (for the allergy lookup)
    """
    badge_html = get_status_badge_html(
        patient['IS_ACTIVE'],
        patient['IS_DECEASED'],
        patient.get('INACTIVE_REASON')
    )

    with st.container(border=True):
        col1, col2, col3, col4 = st.columns([3, 2, 2, 3])

        with col1:
            st.markdown(f"### {patient['SK_PATIENT_ID']} {badge_html}", unsafe_allow_html=True)
            st.caption(f"Person ID {patient['PERSON_ID']}")

        with col2:
            st.markdown(f"**{safe_str(patient['AGE'])}y · {safe_str(patient['GENDER'])}**")
            born = f"Born {format_month_year(patient['BIRTH_DATE_APPROX'])}"
            if patient['IS_DECEASED'] and pd.notna(patient['DEATH_DATE_APPROX']):
                born += f" · Died {format_month_year(patient['DEATH_DATE_APPROX'])}"
            st.caption(born)

        with col3:
            eth_sub = safe_str(patient['ETHNICITY_SUBCATEGORY'])
            eth_cat = safe_str(patient['ETHNICITY_CATEGORY'])
            st.markdown(f"**{eth_sub}**")
            if eth_cat != eth_sub:
                st.caption(eth_cat)

        with col4:
            st.markdown(f"**{safe_str(patient['PRACTICE_NAME'])}**")
            st.caption(f"{safe_str(patient['PRACTICE_CODE'])} · {safe_str(patient['PCN_NAME'])}")

        render_allergies_panel(person_id)


def render_navigation(summary):
    """
    Render navigation cards with record counts.

    Args:
        summary: Record summary dictionary from get_record_summary
    """
    # Count-less Results sits in the shorter second row to keep the grid tidy
    nav_items = [
        ("🗒️ Encounters", f" · {summary['total_encounters']:,}", "encounters"),
        ("📊 Observations", f" · {summary['total_observations']:,}", "observations"),
        ("💊 Medications", f" · {summary['current_medications']:,} current", "medications"),
        ("📅 Appointments", f" · {summary['appointments_last_12m']:,} in 12m", "appointments"),
        ("🧪 Results", "", "results"),
        ("📨 Referrals", f" · {summary['total_referrals']:,}", "referrals"),
        ("🩺 Procedures", f" · {summary['total_procedures']:,}", "procedures"),
        ("🔬 Test Requests", f" · {summary['total_test_requests']:,}", "test_requests"),
    ]

    cols = st.columns(4) + st.columns(4)
    for col, (label, count, page) in zip(cols, nav_items):
        with col:
            if st.button(f"{label}{count}", use_container_width=True, type="primary"):
                st.session_state.page = page
                st.rerun()

    most_recent = max(
        filter(pd.notna, [
            summary['obs_most_recent'],
            summary['med_most_recent'],
            summary['appt_most_recent'],
        ]),
        default=None
    )
    if most_recent is not None:
        st.caption(f"Most recent activity: {format_date(most_recent)}")


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
        eth_sub = safe_str(patient['ETHNICITY_SUBCATEGORY'])
        eth_cat = safe_str(patient['ETHNICITY_CATEGORY'])
        st.markdown(eth_sub)
        if eth_cat != eth_sub:
            st.markdown(f"<small>{eth_cat}</small>", unsafe_allow_html=True)

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

    with st.container(border=True):
        st.markdown("#### Long-Term Conditions")

        if ltc_data.empty:
            st.caption("Not on any condition register")
            return

        # One compact line per clinical domain, split across two columns
        domains = sorted(ltc_data['CLINICAL_DOMAIN'].unique())
        columns = st.columns(2) if len(domains) > 1 else [st.container()]

        for i, domain in enumerate(domains):
            domain_conditions = ltc_data[ltc_data['CLINICAL_DOMAIN'] == domain]

            badges_html = ""
            for _, condition in domain_conditions.iterrows():
                qof_class = "condition-qof" if condition['IS_QOF'] else "condition-other"
                qof_badge = ' <span style="background-color: #084298; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.75rem; margin-left: 4px;">QOF</span>' if condition['IS_QOF'] else ""
                earliest = format_date(condition['EARLIEST_DIAGNOSIS_DATE'])
                badges_html += f'<span class="condition-badge {qof_class}">{condition["CONDITION_NAME"]}{qof_badge} <small>· Dx {earliest}</small></span>'

            with columns[i % len(columns)]:
                st.markdown(
                    f'<span style="font-weight: 600; margin-right: 8px;">{domain}</span>{badges_html}',
                    unsafe_allow_html=True
                )


def _value_or(value, default="Not recorded"):
    """Display value, or a default when missing."""
    if value is None or pd.isna(value):
        return default
    return safe_str(value)


def render_health_status(person_id):
    """
    Render health status & prevention tabs from the reporting marts.

    Args:
        person_id: Person identifier
    """
    from services.status_service import get_person_health_status

    with st.container(border=True):
        return _render_health_status_body(person_id, get_person_health_status)


def _render_health_status_body(person_id, get_person_health_status):
    """
    Body of the health status panel (inside its bordered container).

    Returns:
        The problems tab container, filled at the end of the page run
        so its query never blocks the initial paint.
    """
    st.markdown("#### Health Status & Prevention")

    tab_risk, tab_results, tab_bp, tab_poly, tab_problems, tab_screen, tab_vacc = st.tabs([
        "🚬 Risk Factors", "🧪 Key Results", "🩸 Blood Pressure", "💊 Polypharmacy",
        "🏥 Problems", "🔬 Screening", "💉 Vaccinations"
    ])

    with tab_problems:
        problems_slot = st.container()

    with tab_results:
        render_key_results_tab(person_id)

    status = get_person_health_status(person_id)

    if status is None:
        for tab in (tab_risk, tab_bp, tab_poly, tab_screen, tab_vacc):
            with tab:
                st.info("No health status data available")
        return problems_slot

    with tab_risk:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            bmi = status['BRF_BMI_VALUE']
            st.metric("BMI", f"{bmi:.1f}" if pd.notna(bmi) else "Not recorded")
            st.caption(_value_or(status['BRF_BMI_CATEGORY'], ""))
        with col2:
            st.metric("Smoking", _value_or(status['BRF_SMOKING_STATUS']))
        with col3:
            st.metric("Alcohol", _value_or(status['BRF_ALCOHOL_STATUS']))
        with col4:
            ccms = status['CCMS_SCORE']
            st.metric("Comorbidity Score", f"{ccms:.2f}" if pd.notna(ccms) else "Not scored")
            if pd.notna(status['CCMS_LAST_UPDATED']):
                st.caption(f"Cambridge score, updated {format_date(status['CCMS_LAST_UPDATED'])}")
            else:
                st.caption("Cambridge score")

    with tab_bp:
        if pd.isna(status['BP_LATEST_DATE']):
            st.info("No blood pressure data available")
        else:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Latest BP", f"{status['BP_SYSTOLIC']:.0f}/{status['BP_DIASTOLIC']:.0f}")
                st.caption(format_date(status['BP_LATEST_DATE']))
            with col2:
                sys_t, dia_t = status['BP_SYSTOLIC_THRESHOLD'], status['BP_DIASTOLIC_THRESHOLD']
                target = f"{sys_t:.0f}/{dia_t:.0f}" if pd.notna(sys_t) and pd.notna(dia_t) else "N/A"
                st.metric("Target (NG136)", target)
                st.caption(_value_or(status['BP_PATIENT_GROUP'], ""))
            with col3:
                controlled = status['BP_IS_CONTROLLED']
                st.metric("Controlled", "Yes" if controlled == True else ("No" if controlled == False else "N/A"))
                if status['BP_IS_DIAGNOSED_HTN'] == True:
                    st.caption("Diagnosed hypertension")
            with col4:
                st.metric("Stage", _value_or(status['BP_HYPERTENSION_STAGE'], "N/A"))
            interval = status['BP_MONITORING_INTERVAL']
            if pd.notna(interval):
                within = status['BP_WITHIN_INTERVAL']
                within_text = "within interval" if within == True else "outside interval"
                st.caption(f"Recommended monitoring: {safe_str(interval)} ({within_text})")

    with tab_poly:
        if pd.isna(status['POLY_MEDICATION_COUNT']):
            st.info("No current repeat medications recorded")
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Current Medications", int(status['POLY_MEDICATION_COUNT']))
                st.caption(_value_or(status['POLY_MEDICATION_COUNT_BAND'], ""))
            with col2:
                st.metric("Polypharmacy (5+)", "Yes" if status['POLY_IS_5PLUS'] == True else "No")
            with col3:
                st.metric("Polypharmacy (10+)", "Yes" if status['POLY_IS_10PLUS'] == True else "No")
            if pd.notna(status['POLY_STATUS_DATE']):
                st.caption(f"As at {format_date(status['POLY_STATUS_DATE'])} (repeat prescriptions with active supply)")
            # Snowflake ARRAY arrives as a JSON string (or NaN when absent)
            med_list = status['POLY_MEDICATION_NAME_LIST']
            if med_list is not None and not (isinstance(med_list, float) and pd.isna(med_list)):
                with st.expander("Medication list"):
                    st.write(med_list)

    with tab_screen:
        rows = []
        for label, prefix in [("Cervical", "CERV"), ("Bowel", "BOWEL"), ("Breast", "BREAST")]:
            eligible = status[f'{prefix}_ELIGIBLE']
            if eligible != True:
                rows.append({"Programme": label, "Status": "Not eligible",
                             "Last Completed": "", "Next Due": "", "Days Overdue": ""})
            else:
                overdue = status[f'{prefix}_DAYS_OVERDUE']
                rows.append({
                    "Programme": label,
                    "Status": _value_or(status[f'{prefix}_STATUS'], "Unknown"),
                    "Last Completed": format_date(status[f'{prefix}_LAST_COMPLETED']),
                    "Next Due": format_date(status[f'{prefix}_NEXT_DUE']),
                    "Days Overdue": f"{int(overdue):,}" if pd.notna(overdue) and overdue > 0 else "",
                })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab_vacc:
        rows = []
        for label, prefix, has_eligible in [
            ("Pneumococcal", "PNEUMO", False),
            ("RSV", "RSV", True),
            ("Shingles", "SHINGLES", True),
        ]:
            if has_eligible and status[f'{prefix}_ELIGIBLE'] != True and pd.isna(status[f'{prefix}_STATUS']):
                rows.append({"Vaccination": label, "Campaign": "", "Status": "Not eligible", "Date": ""})
                continue
            if pd.isna(status[f'{prefix}_STATUS']) and pd.isna(status[f'{prefix}_CAMPAIGN']):
                rows.append({"Vaccination": label, "Campaign": "", "Status": "No record", "Date": ""})
                continue
            rows.append({
                "Vaccination": label,
                "Campaign": _value_or(status[f'{prefix}_CAMPAIGN'], ""),
                "Status": _value_or(status[f'{prefix}_STATUS'], "Unknown"),
                "Date": format_date(status[f'{prefix}_DATE']),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption("Latest campaign per programme; age-based eligibility applies (pneumococcal/shingles 65+, RSV 60+)")

    return problems_slot


def render_allergies_panel(person_id):
    """
    Render allergies as a compact EPR-style status line: red inline list
    when allergies exist (details in an expander), a single line otherwise.

    'No known allergy' records are statements of absence, so they are
    separated from actual allergy records rather than listed alongside
    them. No inference is made when both exist - both are shown.

    Args:
        person_id: Person identifier
    """
    from services.record_service import get_patient_allergies
    from utils.helpers import format_practitioner_name

    allergies = get_patient_allergies(person_id)

    if allergies.empty:
        st.markdown("**Allergies:** :orange[No allergy information recorded]")
        return

    # Statements of absence ('No known allergy', 'No known drug allergy', ...)
    is_nka = allergies['ALLERGY_DISPLAY'].str.lower().str.startswith('no known', na=False)
    actual = allergies[~is_nka]
    nka = allergies[is_nka]

    if actual.empty:
        latest_nka = format_date(nka['CLINICAL_EFFECTIVE_DATE'].max())
        st.markdown(f"**Allergies:** No known allergies · last recorded {latest_nka}")
        return

    # Deduplicated names for the inline list; full records in the expander
    names = []
    for _, row in actual.iterrows():
        name = ("🔒 " if row['IS_CONFIDENTIAL'] else "") + safe_str(row['ALLERGY_DISPLAY'])
        if name not in names:
            names.append(name)

    st.markdown(f"**⚠️ Allergies:** :red[{', '.join(names)}]")

    with st.expander(f"Allergy details ({len(actual):,} record(s))"):
        display_df = actual.copy()
        display_df['DATE_DISPLAY'] = display_df['CLINICAL_EFFECTIVE_DATE'].apply(format_date)
        display_df['ALLERGY'] = display_df.apply(
            lambda row: ("🔒 " if row['IS_CONFIDENTIAL'] else "") + safe_str(row['ALLERGY_DISPLAY']),
            axis=1
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

        display_df = display_df[['DATE_DISPLAY', 'ALLERGY', 'PRACTITIONER']]
        display_df.columns = ['Date', 'Allergy / Intolerance', 'Recorded By']

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

        if display_df['Allergy / Intolerance'].str.startswith('🔒').any():
            st.caption("🔒 marks records flagged confidential in the source system")

        if not nka.empty:
            latest_nka = format_date(nka['CLINICAL_EFFECTIVE_DATE'].max())
            st.caption(f"'No known allergy' was also recorded for this patient, most recently {latest_nka}")


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
            row['PRACTITIONER_TITLE'],
            row['PRACTITIONER_ROLE']
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


def render_key_results_tab(person_id):
    """
    Render latest key results from the curated biomarker models.

    Args:
        person_id: Person identifier
    """
    from services.status_service import get_person_biomarkers

    biomarkers = get_person_biomarkers(person_id)

    if biomarkers is None:
        st.info("No key results available")
        return

    def fmt(value, pattern):
        return pattern.format(value) if pd.notna(value) else None

    b = biomarkers
    hb_value = (
        f"{b['HB_VALUE']:.0f} {_value_or(b['HB_UNIT'], '')}".strip()
        if pd.notna(b['HB_VALUE']) else None
    )
    rows = [
        ("HbA1c", _value_or(b['HBA1C_VALUE'], None), _value_or(b['HBA1C_CATEGORY'], ""), b['HBA1C_DATE']),
        ("Total cholesterol", fmt(b['CHOL_VALUE'], "{:.1f} mmol/L"), _value_or(b['CHOL_CATEGORY'], ""), b['CHOL_DATE']),
        ("LDL cholesterol", fmt(b['LDL_VALUE'], "{:.1f} mmol/L"),
         (f"CVD target: {safe_str(b['LDL_TARGET_MET'])}" if pd.notna(b['LDL_TARGET_MET']) else ""),
         b['LDL_DATE']),
        ("eGFR", fmt(b['EGFR_VALUE'], "{:.0f} mL/min/1.73m²"), _value_or(b['EGFR_CKD_STAGE'], ""), b['EGFR_DATE']),
        ("Creatinine", fmt(b['CREATININE_VALUE'], "{:.0f} µmol/L"), _value_or(b['CREATININE_CATEGORY'], ""), b['CREATININE_DATE']),
        ("Urine ACR", fmt(b['ACR_VALUE'], "{:.1f} mg/mmol"), _value_or(b['ACR_CATEGORY'], ""), b['ACR_DATE']),
        ("Haemoglobin", hb_value, _value_or(b['HB_CATEGORY'], ""), b['HB_DATE']),
        ("Blood glucose", _value_or(b['GLUCOSE_VALUE'], None),
         ("Fasting" if b['GLUCOSE_IS_FASTING'] == True else ""), b['GLUCOSE_DATE']),
        (f"QRISK{'' if pd.isna(b['QRISK_TYPE']) else ' (' + safe_str(b['QRISK_TYPE']) + ')'}",
         fmt(b['QRISK_SCORE'], "{:.1f}%"), _value_or(b['QRISK_CATEGORY'], ""), b['QRISK_DATE']),
    ]

    table_rows = [
        {"Result": name, "Latest Value": value, "Interpretation": interp,
         "Date": format_date(date)}
        for name, value, interp, date in rows
        if value is not None and value != "Not recorded"
    ]

    if not table_rows:
        st.info("No key results recorded for this patient")
        return

    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
    st.caption(
        "Latest value per biomarker from the curated observation models "
        "(unit-standardised); interpretation categories are derived in the analytics pipeline. "
        "Full history on the Results page."
    )


def render_problems_tab(person_id):
    """
    Render the problems tab content. Called at the end of the page run
    (after everything else has painted) so the query, cached thereafter,
    never blocks the initial render.

    Args:
        person_id: Person identifier
    """
    from services.record_service import get_patient_problems

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

    st.markdown(f"**Current problems ({len(active_problems):,})**")
    if active_problems.empty:
        st.caption("No current problems")
    else:
        render_problems_table(active_problems)

    st.markdown(f"**Past problems ({len(past_problems):,})**")
    if past_problems.empty:
        st.caption("No past problems")
    else:
        render_problems_table(past_problems)
