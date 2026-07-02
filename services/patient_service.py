"""
Patient search and demographics service

Patient identifiers are validated integers inlined as SQL literals
(injection-safe) so Snowflake query history records which patient was
accessed - bind placeholders would hide the value from the audit trail.
Free-text input is always bound.
"""

import streamlit as st
import pandas as pd
from config import TABLE_DIM_PERSON, TABLE_DIM_PERSON_HISTORICAL, TABLE_LTC_SUMMARY
from database import run_query


def search_patient(search_term):
    """
    Search for a patient by sk_patient_id or person_id (both numeric).

    Args:
        search_term: sk_patient_id or person_id

    Returns:
        DataFrame with patient search results
    """
    try:
        search_int = int(str(search_term).strip())
    except (ValueError, TypeError):
        st.warning("Patient identifiers are numeric - enter an sk_patient_id or person_id")
        return pd.DataFrame()

    query = f"""
    SELECT
        person_id,
        sk_patient_id,
        age,
        gender,
        birth_date_approx,
        is_active,
        is_deceased,
        inactive_reason,
        practice_name,
        pcn_name,
        ethnicity_subcategory
    FROM {TABLE_DIM_PERSON}
    WHERE sk_patient_id = {search_int} OR person_id = {search_int}
    """

    try:
        return run_query(query)
    except Exception as e:
        st.error(f"Error searching for patient: {str(e)}")
        return pd.DataFrame()


def get_patient_demographics(sk_patient_id):
    """
    Get full demographics for a patient (single-row point lookup).

    Args:
        sk_patient_id: Patient identifier (sk_patient_id)

    Returns:
        DataFrame with full patient demographics
    """
    query = f"""
    SELECT *
    FROM {TABLE_DIM_PERSON}
    WHERE sk_patient_id = {int(sk_patient_id)}
    """

    try:
        result = run_query(query)
        if result.empty:
            st.error(f"Patient {sk_patient_id} not found")
        return result
    except Exception as e:
        st.error(f"Error loading patient demographics: {str(e)}")
        return pd.DataFrame()


def get_person_id(sk_patient_id):
    """
    Resolve sk_patient_id to person_id.

    Args:
        sk_patient_id: Patient identifier (sk_patient_id)

    Returns:
        person_id as int, or None if not found
    """
    query = f"""
    SELECT person_id
    FROM {TABLE_DIM_PERSON}
    WHERE sk_patient_id = {int(sk_patient_id)}
    LIMIT 1
    """

    try:
        result = run_query(query)
        if result.empty:
            return None
        return int(result.iloc[0]["PERSON_ID"])
    except Exception as e:
        st.error(f"Error resolving person_id: {str(e)}")
        return None


def get_patient_registration_history(person_id):
    """
    Get registration history (SCD-2 periods) for a person.

    Args:
        person_id: Person identifier

    Returns:
        DataFrame with registration history
    """
    query = f"""
    SELECT
        effective_start_date,
        effective_end_date,
        is_current,
        period_sequence,
        is_active,
        practice_name,
        practice_code,
        pcn_name,
        registration_start_date,
        registration_end_date,
        ethnicity_subcategory,
        borough_registered,
        borough_resident,
        local_authority_name
    FROM {TABLE_DIM_PERSON_HISTORICAL}
    WHERE person_id = {int(person_id)}
    ORDER BY effective_start_date DESC
    """

    try:
        return run_query(query)
    except Exception as e:
        st.warning(f"Could not load registration history: {str(e)}")
        return pd.DataFrame()


def get_patient_ltc_summary(person_id):
    """
    Get long-term conditions on-register summary for a person.

    Args:
        person_id: Person identifier

    Returns:
        DataFrame with LTC conditions
    """
    query = f"""
    SELECT
        condition_code,
        condition_name,
        clinical_domain,
        is_on_register,
        is_qof,
        earliest_diagnosis_date,
        latest_diagnosis_date
    FROM {TABLE_LTC_SUMMARY}
    WHERE person_id = {int(person_id)}
        AND is_on_register = TRUE
    ORDER BY
        is_qof DESC,
        clinical_domain,
        condition_name
    """

    try:
        return run_query(query)
    except Exception as e:
        st.warning(f"Could not load LTC summary: {str(e)}")
        return pd.DataFrame()
