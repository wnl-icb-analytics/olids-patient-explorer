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
    TABLE_CONCEPT,
    TABLE_APPOINTMENT,
    TABLE_APPOINTMENT_PRACTITIONER,
    MAX_OBSERVATIONS,
)
from database import run_query

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
        appt.appt_most_recent
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
    """

    try:
        pid = int(person_id)
        result = run_query(query, [pid, pid, pid])
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
        o.id
    FROM {TABLE_OBSERVATION} o
    LEFT JOIN {TABLE_PRACTITIONER} p
        ON o.practitioner_id = p.id
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
        m.id
    FROM {TABLE_MEDICATION_ORDER} m
    LEFT JOIN {TABLE_MEDICATION_STATEMENT} ms
        ON m.medication_statement_id = ms.id
    LEFT JOIN {TABLE_PRACTITIONER} p
        ON m.practitioner_id = p.id
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
        CASE WHEN a.start_date >= CURRENT_TIMESTAMP() THEN TRUE ELSE FALSE END as is_future,
        a.id
    FROM {TABLE_APPOINTMENT} a
    LEFT JOIN {TABLE_APPOINTMENT_PRACTITIONER} ap
        ON a.id = ap.appointment_id
    LEFT JOIN {TABLE_PRACTITIONER} p
        ON ap.practitioner_id = p.id
    WHERE {where_sql}
    ORDER BY a.start_date DESC
    LIMIT {MAX_OBSERVATIONS}
    """

    try:
        return run_query(query, params)
    except Exception as e:
        st.error(f"Error loading appointments: {str(e)}")
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
        o.id
    FROM {TABLE_OBSERVATION} o
    LEFT JOIN {TABLE_PRACTITIONER} p
        ON o.practitioner_id = p.id
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
