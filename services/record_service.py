"""
Patient records service for observations, medications, appointments and problems
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from config import (
    TABLE_OBSERVATION,
    TABLE_MEDICATION_ORDER,
    TABLE_MEDICATION_STATEMENT,
    TABLE_PRACTITIONER,
    TABLE_PRACTITIONER_IN_ROLE,
    TABLE_CONCEPT,
    TABLE_APPOINTMENT,
    TABLE_APPOINTMENT_PRACTITIONER,
    TABLE_ALLERGY,
    TABLE_REFERRAL,
    TABLE_PROCEDURE_REQUEST,
    TABLE_ORGANISATION,
    TABLE_ENCOUNTER,
    TABLE_DIAGNOSTIC_ORDER,
    MAX_OBSERVATIONS,
)
from database import run_query

# One role per practitioner. The source is currently 1:1 with
# practitioners, but QUALIFY guards against row fan-out if employment
# history ever appears in the table.
PRACTITIONER_ROLE_JOIN = f"""LEFT JOIN (
        SELECT practitioner_id, role
        FROM {TABLE_PRACTITIONER_IN_ROLE}
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY practitioner_id
            ORDER BY (date_employment_end IS NULL) DESC, date_employment_start DESC NULLS LAST
        ) = 1
    ) pir
        ON p.id = pir.practitioner_id"""

EMPTY_RECORD_SUMMARY = {
    "total_observations": 0,
    "obs_earliest": None,
    "obs_most_recent": None,
    "total_medications": 0,
    "current_medications": 0,
    "med_earliest": None,
    "med_most_recent": None,
    "total_appointments": 0,
    "appointments_last_12m": 0,
    "appt_earliest": None,
    "appt_most_recent": None,
    "total_referrals": 0,
    "total_procedures": 0,
    "total_encounters": 0,
    "total_test_requests": 0,
}


def get_record_summary(person_id):
    """
    Get observation, medication and appointment summary stats in a single
    round-trip (three single-row aggregates cross-joined).

    Args:
        person_id: Person identifier

    Returns:
        Dictionary with summary stats (EMPTY_RECORD_SUMMARY keys)
    """
    query = f"""
    SELECT
        obs.total_observations,
        obs.obs_earliest,
        obs.obs_most_recent,
        med.total_medications,
        med.current_medications,
        med.med_earliest,
        med.med_most_recent,
        appt.total_appointments,
        appt.appointments_last_12m,
        appt.appt_earliest,
        appt.appt_most_recent,
        ref.total_referrals,
        proc.total_procedures,
        enc.total_encounters,
        diag.total_test_requests
    FROM (
        SELECT
            COUNT(*) as total_observations,
            MIN(clinical_effective_date) as obs_earliest,
            MAX(clinical_effective_date) as obs_most_recent
        FROM {TABLE_OBSERVATION}
        WHERE person_id = ?
    ) obs
    CROSS JOIN (
        SELECT
            COUNT(*) as total_medications,
            MIN(m.clinical_effective_date) as med_earliest,
            MAX(m.clinical_effective_date) as med_most_recent,
            COUNT(CASE
                WHEN ms.cancellation_date IS NOT NULL AND ms.cancellation_date <= CURRENT_DATE() THEN NULL
                WHEN ms.expiry_date IS NOT NULL AND ms.expiry_date < CURRENT_DATE() THEN NULL
                WHEN ms.is_active = FALSE THEN NULL
                WHEN m.duration_days IS NOT NULL
                    AND DATEADD(day, m.duration_days, m.clinical_effective_date) > CURRENT_DATE()
                THEN 1
            END) as current_medications
        FROM {TABLE_MEDICATION_ORDER} m
        LEFT JOIN {TABLE_MEDICATION_STATEMENT} ms
            ON m.medication_statement_id = ms.id
        WHERE m.person_id = ?
    ) med
    CROSS JOIN (
        SELECT
            COUNT(*) as total_appointments,
            MIN(start_date) as appt_earliest,
            MAX(CASE WHEN start_date < CURRENT_TIMESTAMP() THEN start_date END) as appt_most_recent,
            COUNT(CASE
                WHEN start_date >= DATEADD(month, -12, CURRENT_DATE())
                THEN 1
            END) as appointments_last_12m
        FROM {TABLE_APPOINTMENT}
        WHERE person_id = ?
    ) appt
    CROSS JOIN (
        SELECT COUNT(*) as total_referrals
        FROM {TABLE_REFERRAL}
        WHERE person_id = ?
    ) ref
    CROSS JOIN (
        SELECT COUNT(*) as total_procedures
        FROM {TABLE_PROCEDURE_REQUEST}
        WHERE person_id = ?
    ) proc
    CROSS JOIN (
        SELECT COUNT(*) as total_encounters
        FROM {TABLE_ENCOUNTER}
        WHERE person_id = ?
    ) enc
    CROSS JOIN (
        SELECT COUNT(*) as total_test_requests
        FROM {TABLE_DIAGNOSTIC_ORDER}
        WHERE person_id = ?
    ) diag
    """

    try:
        pid = int(person_id)
        result = run_query(query, [pid, pid, pid, pid, pid, pid, pid])
        if result.empty:
            return dict(EMPTY_RECORD_SUMMARY)

        row = result.iloc[0]
        return {
            "total_observations": int(row["TOTAL_OBSERVATIONS"]),
            "obs_earliest": row["OBS_EARLIEST"],
            "obs_most_recent": row["OBS_MOST_RECENT"],
            "total_medications": int(row["TOTAL_MEDICATIONS"]),
            "current_medications": int(row["CURRENT_MEDICATIONS"]),
            "med_earliest": row["MED_EARLIEST"],
            "med_most_recent": row["MED_MOST_RECENT"],
            "total_appointments": int(row["TOTAL_APPOINTMENTS"]),
            "appointments_last_12m": int(row["APPOINTMENTS_LAST_12M"]),
            "appt_earliest": row["APPT_EARLIEST"],
            "appt_most_recent": row["APPT_MOST_RECENT"],
            "total_referrals": int(row["TOTAL_REFERRALS"]),
            "total_procedures": int(row["TOTAL_PROCEDURES"]),
            "total_encounters": int(row["TOTAL_ENCOUNTERS"]),
            "total_test_requests": int(row["TOTAL_TEST_REQUESTS"]),
        }
    except Exception as e:
        st.error(f"Error loading record summary: {str(e)}")
        return dict(EMPTY_RECORD_SUMMARY)


def get_patient_observations(person_id, date_from=None, date_to=None, search_term=""):
    """
    Get observations for a patient with optional filters.

    Args:
        person_id: Person identifier
        date_from: Start date filter (optional)
        date_to: End date filter (optional)
        search_term: Search term for code or description (optional)

    Returns:
        DataFrame with observations
    """
    where_clauses = ["o.person_id = ?"]
    params = [int(person_id)]

    if date_from:
        where_clauses.append("o.clinical_effective_date >= ?")
        params.append(str(date_from))

    if date_to:
        where_clauses.append("o.clinical_effective_date <= ?")
        params.append(str(date_to))

    if search_term and search_term.strip():
        where_clauses.append(
            "(o.mapped_concept_code ILIKE ? OR o.mapped_concept_display ILIKE ?)"
        )
        pattern = f"%{search_term.strip()}%"
        params.extend([pattern, pattern])

    where_sql = " AND ".join(where_clauses)

    query = f"""
    SELECT
        o.clinical_effective_date,
        o.mapped_concept_code,
        o.mapped_concept_display,
        o.result_value,
        o.result_text,
        o.result_unit_display,
        o.is_problem,
        o.is_confidential,
        COALESCE(episodicity_concept.display, o.episodicity_source_concept_id::varchar) as episodicity_display,
        p.surname as practitioner_last_name,
        p.first_name as practitioner_first_name,
        p.title as practitioner_title,
        pir.role as practitioner_role,
        o.id
    FROM {TABLE_OBSERVATION} o
    LEFT JOIN {TABLE_PRACTITIONER} p
        ON o.practitioner_id = p.id
    {PRACTITIONER_ROLE_JOIN}
    LEFT JOIN {TABLE_CONCEPT} episodicity_concept
        ON o.episodicity_source_concept_id = episodicity_concept.concept_id
    WHERE {where_sql}
    ORDER BY o.clinical_effective_date DESC
    LIMIT {MAX_OBSERVATIONS}
    """

    try:
        return run_query(query, params)
    except Exception as e:
        st.error(f"Error loading observations: {str(e)}")
        return pd.DataFrame()


def get_patient_medications(person_id, date_from=None, date_to=None, search_term="", current_only=False):
    """
    Get medications for a patient with optional filters.

    Args:
        person_id: Person identifier
        date_from: Start date filter (optional)
        date_to: End date filter (optional)
        search_term: Search term for code or description (optional)
        current_only: If True, only return current/active medications (default False)

    Returns:
        DataFrame with medications
    """
    where_clauses = ["m.person_id = ?"]
    params = [int(person_id)]

    if date_from:
        where_clauses.append("m.clinical_effective_date >= ?")
        params.append(str(date_from))

    if date_to:
        where_clauses.append("m.clinical_effective_date <= ?")
        params.append(str(date_to))

    if search_term and search_term.strip():
        where_clauses.append(
            "(m.mapped_concept_code ILIKE ? OR m.mapped_concept_display ILIKE ?)"
        )
        pattern = f"%{search_term.strip()}%"
        params.extend([pattern, pattern])

    # Filter for current medications only
    if current_only:
        where_clauses.append("""
            (ms.cancellation_date IS NULL OR ms.cancellation_date > CURRENT_DATE())
            AND (ms.expiry_date IS NULL OR ms.expiry_date >= CURRENT_DATE())
            AND (ms.is_active IS NULL OR ms.is_active = TRUE)
            AND (
                m.duration_days IS NULL
                OR DATEADD(day, m.duration_days, m.clinical_effective_date) >= CURRENT_DATE()
            )
        """)

    where_sql = " AND ".join(where_clauses)

    query = f"""
    SELECT
        m.clinical_effective_date,
        m.mapped_concept_code,
        m.mapped_concept_display,
        m.dose,
        m.quantity_value,
        m.quantity_unit,
        m.duration_days,
        m.estimated_cost,
        m.issue_method_description,
        m.is_confidential,
        ms.bnf_reference,
        ms.authorisation_type_display,
        ms.is_active as statement_is_active,
        ms.cancellation_date,
        ms.expiry_date,
        p.surname as practitioner_last_name,
        p.first_name as practitioner_first_name,
        p.title as practitioner_title,
        pir.role as practitioner_role,
        m.id
    FROM {TABLE_MEDICATION_ORDER} m
    LEFT JOIN {TABLE_MEDICATION_STATEMENT} ms
        ON m.medication_statement_id = ms.id
    LEFT JOIN {TABLE_PRACTITIONER} p
        ON m.practitioner_id = p.id
    {PRACTITIONER_ROLE_JOIN}
    WHERE {where_sql}
    ORDER BY m.clinical_effective_date DESC
    LIMIT {MAX_OBSERVATIONS}
    """

    try:
        return run_query(query, params)
    except Exception as e:
        st.error(f"Error loading medications: {str(e)}")
        return pd.DataFrame()


def calculate_date_range(range_option):
    """
    Calculate date range based on selection.

    Args:
        range_option: Selected date range option

    Returns:
        Tuple of (date_from, date_to) or (None, None) for all time
    """
    from config import DATE_RANGE_OPTIONS

    days = DATE_RANGE_OPTIONS.get(range_option)

    if days is None:
        return None, None

    date_to = datetime.now().date()
    date_from = date_to - timedelta(days=days)

    return date_from, date_to


def get_patient_appointments(person_id, date_from=None, date_to=None, include_future=True):
    """
    Get appointments for a patient with optional filters.

    Args:
        person_id: Person identifier
        date_from: Start date filter (optional)
        date_to: End date filter (optional)
        include_future: Include future appointments regardless of date_from (default True)

    Returns:
        DataFrame with appointments
    """
    where_clauses = ["a.person_id = ?"]
    params = [int(person_id)]

    if date_from:
        if include_future:
            where_clauses.append("(a.start_date >= ? OR a.start_date >= CURRENT_TIMESTAMP())")
        else:
            where_clauses.append("a.start_date >= ?")
        params.append(str(date_from))

    if date_to:
        where_clauses.append("a.start_date <= ?")
        params.append(str(date_to))

    where_sql = " AND ".join(where_clauses)

    query = f"""
    SELECT
        a.start_date,
        a.appointment_type as type,
        a.appointment_status_display as appointment_status,
        a.national_slot_category_name,
        a.contact_mode_display as contact_mode,
        a.planned_duration_mins as planned_duration,
        a.actual_duration_mins as actual_duration,
        a.patient_wait_mins as patient_wait,
        p.surname as practitioner_last_name,
        p.first_name as practitioner_first_name,
        p.title as practitioner_title,
        pir.role as practitioner_role,
        CASE WHEN a.start_date >= CURRENT_TIMESTAMP() THEN TRUE ELSE FALSE END as is_future,
        a.id
    FROM {TABLE_APPOINTMENT} a
    LEFT JOIN {TABLE_APPOINTMENT_PRACTITIONER} ap
        ON a.id = ap.appointment_id
    LEFT JOIN {TABLE_PRACTITIONER} p
        ON ap.practitioner_id = p.id
    {PRACTITIONER_ROLE_JOIN}
    WHERE {where_sql}
    ORDER BY a.start_date DESC
    LIMIT {MAX_OBSERVATIONS}
    """

    try:
        return run_query(query, params)
    except Exception as e:
        st.error(f"Error loading appointments: {str(e)}")
        return pd.DataFrame()


def get_patient_allergies(person_id):
    """
    Get allergy and intolerance records for a patient.

    Includes 'No known allergy' style records (statements of absence);
    callers separate these from actual allergies for display.
    clinical_status/verification_status/category are not selected as they
    are unpopulated in the source.

    Args:
        person_id: Person identifier

    Returns:
        DataFrame with allergy records
    """
    query = f"""
    SELECT
        a.clinical_effective_date,
        a.mapped_concept_code,
        COALESCE(a.mapped_concept_display, a.source_display) as allergy_display,
        a.is_confidential,
        p.surname as practitioner_last_name,
        p.first_name as practitioner_first_name,
        p.title as practitioner_title,
        pir.role as practitioner_role,
        a.id
    FROM {TABLE_ALLERGY} a
    LEFT JOIN {TABLE_PRACTITIONER} p
        ON a.practitioner_id = p.id
    {PRACTITIONER_ROLE_JOIN}
    WHERE a.person_id = ?
    ORDER BY a.clinical_effective_date DESC
    """

    try:
        return run_query(query, [int(person_id)])
    except Exception as e:
        st.error(f"Error loading allergies: {str(e)}")
        return pd.DataFrame()


def get_patient_referrals(person_id):
    """
    Get referral requests for a patient.

    Referral reason and priority resolve via CONCEPT; priority is only
    ~24% populated so displays blank when absent (no UUID fallback).
    Specialty is unpopulated in the source and not selected.

    Args:
        person_id: Person identifier

    Returns:
        DataFrame with referrals
    """
    query = f"""
    SELECT
        r.clinical_effective_date,
        referral_concept.display as referral_display,
        priority_concept.display as priority,
        type_concept.display as referral_type,
        r.mode,
        r.is_outgoing_referral,
        r.unique_booking_reference_number as ubrn,
        req_org.name as requester_org,
        rec_org.name as recipient_org,
        p.surname as practitioner_last_name,
        p.first_name as practitioner_first_name,
        p.title as practitioner_title,
        pir.role as practitioner_role,
        r.id
    FROM {TABLE_REFERRAL} r
    LEFT JOIN {TABLE_CONCEPT} referral_concept
        ON r.referral_request_source_concept_id = referral_concept.concept_id
    LEFT JOIN {TABLE_CONCEPT} priority_concept
        ON r.referral_request_priority_source_concept_id = priority_concept.concept_id
    LEFT JOIN {TABLE_CONCEPT} type_concept
        ON r.referral_request_type_source_concept_id = type_concept.concept_id
    LEFT JOIN {TABLE_ORGANISATION} req_org
        ON r.requester_organisation_id = req_org.id
    LEFT JOIN {TABLE_ORGANISATION} rec_org
        ON r.recipient_organisation_id = rec_org.id
    LEFT JOIN {TABLE_PRACTITIONER} p
        ON r.practitioner_id = p.id
    {PRACTITIONER_ROLE_JOIN}
    WHERE r.person_id = ?
    ORDER BY r.clinical_effective_date DESC
    LIMIT {MAX_OBSERVATIONS}
    """

    try:
        return run_query(query, [int(person_id)])
    except Exception as e:
        st.error(f"Error loading referrals: {str(e)}")
        return pd.DataFrame()


def get_patient_procedures(person_id):
    """
    Get procedure requests for a patient.

    Args:
        person_id: Person identifier

    Returns:
        DataFrame with procedure requests
    """
    query = f"""
    SELECT
        pr.clinical_effective_date,
        COALESCE(pr.description, proc_concept.display) as procedure_display,
        status_concept.display as status,
        pr.is_confidential,
        p.surname as practitioner_last_name,
        p.first_name as practitioner_first_name,
        p.title as practitioner_title,
        pir.role as practitioner_role,
        pr.id
    FROM {TABLE_PROCEDURE_REQUEST} pr
    LEFT JOIN {TABLE_CONCEPT} proc_concept
        ON pr.procedure_request_source_concept_id = proc_concept.concept_id
    LEFT JOIN {TABLE_CONCEPT} status_concept
        ON pr.status_source_concept_id = status_concept.concept_id
    LEFT JOIN {TABLE_PRACTITIONER} p
        ON pr.practitioner_id = p.id
    {PRACTITIONER_ROLE_JOIN}
    WHERE pr.person_id = ?
    ORDER BY pr.clinical_effective_date DESC
    LIMIT {MAX_OBSERVATIONS}
    """

    try:
        return run_query(query, [int(person_id)])
    except Exception as e:
        st.error(f"Error loading procedures: {str(e)}")
        return pd.DataFrame()


def get_patient_encounters(person_id, date_from=None):
    """
    Get encounters (consultations) for a patient.

    Args:
        person_id: Person identifier
        date_from: Start date filter (optional)

    Returns:
        DataFrame with encounters
    """
    where_clauses = ["e.person_id = ?"]
    params = [int(person_id)]

    if date_from:
        where_clauses.append("e.clinical_effective_date >= ?")
        params.append(str(date_from))

    where_sql = " AND ".join(where_clauses)

    query = f"""
    SELECT
        e.id,
        e.clinical_effective_date,
        enc_concept.display as encounter_type,
        e.location,
        p.surname as practitioner_last_name,
        p.first_name as practitioner_first_name,
        p.title as practitioner_title,
        pir.role as practitioner_role
    FROM {TABLE_ENCOUNTER} e
    LEFT JOIN {TABLE_CONCEPT} enc_concept
        ON e.encounter_source_concept_id = enc_concept.concept_id
    LEFT JOIN {TABLE_PRACTITIONER} p
        ON e.practitioner_id = p.id
    {PRACTITIONER_ROLE_JOIN}
    WHERE {where_sql}
    ORDER BY e.clinical_effective_date DESC
    LIMIT {MAX_OBSERVATIONS}
    """

    try:
        return run_query(query, params)
    except Exception as e:
        st.error(f"Error loading consultations: {str(e)}")
        return pd.DataFrame()


def get_patient_encounter_items(person_id, date_from=None):
    """
    Get clinical events (observations, medication orders, referrals,
    procedure requests) with their encounter linkage, for grouping into
    a consultation view. One UNION ALL round-trip.

    Args:
        person_id: Person identifier
        date_from: Start date filter (optional)

    Returns:
        DataFrame with columns ITEM_TYPE, ENCOUNTER_ID,
        CLINICAL_EFFECTIVE_DATE, DETAIL, DETAIL_VALUE, IS_CONFIDENTIAL
    """
    pid = int(person_id)
    date_filter = ""
    branch_params = [pid]
    if date_from:
        date_filter = "AND clinical_effective_date >= ?"
        branch_params.append(str(date_from))

    query = f"""
    SELECT
        'Observation' as item_type,
        encounter_id,
        clinical_effective_date,
        mapped_concept_display as detail,
        CASE
            WHEN result_value IS NOT NULL
            THEN result_value::varchar || COALESCE(' ' || result_unit_display, '')
            ELSE result_text
        END as detail_value,
        is_confidential
    FROM {TABLE_OBSERVATION}
    WHERE person_id = ? {date_filter}

    UNION ALL

    SELECT
        'Medication',
        encounter_id,
        clinical_effective_date,
        mapped_concept_display,
        dose,
        is_confidential
    FROM {TABLE_MEDICATION_ORDER}
    WHERE person_id = ? {date_filter}

    UNION ALL

    SELECT
        'Referral',
        r.encounter_id,
        r.clinical_effective_date,
        referral_concept.display,
        priority_concept.display,
        FALSE
    FROM {TABLE_REFERRAL} r
    LEFT JOIN {TABLE_CONCEPT} referral_concept
        ON r.referral_request_source_concept_id = referral_concept.concept_id
    LEFT JOIN {TABLE_CONCEPT} priority_concept
        ON r.referral_request_priority_source_concept_id = priority_concept.concept_id
    WHERE r.person_id = ? {date_filter.replace('clinical_effective_date', 'r.clinical_effective_date')}

    UNION ALL

    SELECT
        'Procedure request',
        pr.encounter_id,
        pr.clinical_effective_date,
        COALESCE(pr.description, proc_concept.display),
        status_concept.display,
        pr.is_confidential
    FROM {TABLE_PROCEDURE_REQUEST} pr
    LEFT JOIN {TABLE_CONCEPT} proc_concept
        ON pr.procedure_request_source_concept_id = proc_concept.concept_id
    LEFT JOIN {TABLE_CONCEPT} status_concept
        ON pr.status_source_concept_id = status_concept.concept_id
    WHERE pr.person_id = ? {date_filter.replace('clinical_effective_date', 'pr.clinical_effective_date')}

    UNION ALL

    SELECT
        'Test request',
        d.encounter_id,
        d.clinical_effective_date,
        test_concept.display,
        CASE
            WHEN d.result_value IS NOT NULL THEN d.result_value::varchar
            ELSE d.result_text
        END,
        FALSE
    FROM {TABLE_DIAGNOSTIC_ORDER} d
    LEFT JOIN {TABLE_CONCEPT} test_concept
        ON d.diagnostic_order_source_concept_id = test_concept.concept_id
    WHERE d.person_id = ? {date_filter.replace('clinical_effective_date', 'd.clinical_effective_date')}

    ORDER BY clinical_effective_date DESC
    LIMIT {MAX_OBSERVATIONS}
    """

    try:
        return run_query(query, branch_params * 5)
    except Exception as e:
        st.error(f"Error loading consultation items: {str(e)}")
        return pd.DataFrame()


def get_patient_test_requests(person_id):
    """
    Get test requests (diagnostic orders) for a patient.

    The source table's person_id is currently NULL pending an upstream
    backfill, so this returns no rows until that lands - the query is
    correct for the populated table.

    Args:
        person_id: Person identifier

    Returns:
        DataFrame with test requests
    """
    query = f"""
    SELECT
        d.clinical_effective_date,
        test_concept.display as test_display,
        CASE
            WHEN d.result_value IS NOT NULL THEN d.result_value::varchar
            ELSE d.result_text
        END as result_display,
        d.result_date,
        p.surname as practitioner_last_name,
        p.first_name as practitioner_first_name,
        p.title as practitioner_title,
        pir.role as practitioner_role,
        d.id
    FROM {TABLE_DIAGNOSTIC_ORDER} d
    LEFT JOIN {TABLE_CONCEPT} test_concept
        ON d.diagnostic_order_source_concept_id = test_concept.concept_id
    LEFT JOIN {TABLE_PRACTITIONER} p
        ON d.practitioner_id = p.id
    {PRACTITIONER_ROLE_JOIN}
    WHERE d.person_id = ?
    ORDER BY d.clinical_effective_date DESC
    LIMIT {MAX_OBSERVATIONS}
    """

    try:
        return run_query(query, [int(person_id)])
    except Exception as e:
        st.error(f"Error loading test requests: {str(e)}")
        return pd.DataFrame()


def get_patient_result_types(person_id):
    """
    Get the distinct numeric result types recorded for a patient
    (observations with a result_value), with counts and latest date.

    Args:
        person_id: Person identifier

    Returns:
        DataFrame with RESULT_DISPLAY, RESULT_COUNT, LATEST_DATE
    """
    query = f"""
    SELECT
        mapped_concept_display as result_display,
        COUNT(*) as result_count,
        MAX(clinical_effective_date) as latest_date
    FROM {TABLE_OBSERVATION}
    WHERE person_id = ?
        AND result_value IS NOT NULL
        AND mapped_concept_display IS NOT NULL
    GROUP BY mapped_concept_display
    ORDER BY result_count DESC, latest_date DESC
    """

    try:
        return run_query(query, [int(person_id)])
    except Exception as e:
        st.error(f"Error loading result types: {str(e)}")
        return pd.DataFrame()


def get_patient_result_series(person_id, result_display):
    """
    Get the full history of a numeric result type for a patient.

    Args:
        person_id: Person identifier
        result_display: mapped_concept_display of the result type

    Returns:
        DataFrame with dates, values and units, most recent first
    """
    query = f"""
    SELECT
        o.clinical_effective_date,
        o.result_value,
        o.result_unit_display,
        o.is_confidential,
        p.surname as practitioner_last_name,
        p.first_name as practitioner_first_name,
        p.title as practitioner_title,
        pir.role as practitioner_role
    FROM {TABLE_OBSERVATION} o
    LEFT JOIN {TABLE_PRACTITIONER} p
        ON o.practitioner_id = p.id
    {PRACTITIONER_ROLE_JOIN}
    WHERE o.person_id = ?
        AND o.result_value IS NOT NULL
        AND o.mapped_concept_display = ?
    ORDER BY o.clinical_effective_date DESC
    LIMIT {MAX_OBSERVATIONS}
    """

    try:
        return run_query(query, [int(person_id), str(result_display)])
    except Exception as e:
        st.error(f"Error loading result history: {str(e)}")
        return pd.DataFrame()


def get_patient_problems(person_id):
    """
    Get active and past problems for a patient from observations table.

    Args:
        person_id: Person identifier

    Returns:
        DataFrame with problems including episodicity
    """
    query = f"""
    SELECT
        o.clinical_effective_date,
        o.mapped_concept_code,
        o.mapped_concept_display,
        o.is_problem,
        o.is_confidential,
        o.problem_end_date,
        COALESCE(episodicity_concept.display, o.episodicity_source_concept_id::varchar) as episodicity,
        p.surname as practitioner_last_name,
        p.first_name as practitioner_first_name,
        p.title as practitioner_title,
        pir.role as practitioner_role,
        o.id
    FROM {TABLE_OBSERVATION} o
    LEFT JOIN {TABLE_PRACTITIONER} p
        ON o.practitioner_id = p.id
    {PRACTITIONER_ROLE_JOIN}
    LEFT JOIN {TABLE_CONCEPT} episodicity_concept
        ON o.episodicity_source_concept_id = episodicity_concept.concept_id
    WHERE o.person_id = ?
        AND o.is_problem = TRUE
        AND (o.is_problem_deleted IS NULL OR o.is_problem_deleted = FALSE)
    ORDER BY o.clinical_effective_date DESC
    LIMIT {MAX_OBSERVATIONS}
    """

    try:
        return run_query(query, [int(person_id)])
    except Exception as e:
        st.error(f"Error loading problems: {str(e)}")
        return pd.DataFrame()
