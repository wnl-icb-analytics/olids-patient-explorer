"""
Person-level health status service (reporting-layer analytics marts)
"""

import streamlit as st
import pandas as pd
from config import (
    TABLE_RISK_FACTORS,
    TABLE_POLYPHARMACY,
    TABLE_BP_CONTROL,
    TABLE_CCMS,
    TABLE_CERVICAL_SCREENING,
    TABLE_BOWEL_SCREENING,
    TABLE_BREAST_SCREENING,
    TABLE_PNEUMOCOCCAL,
    TABLE_RSV,
    TABLE_SHINGLES,
)
from database import run_query


def get_person_health_status(person_id):
    """
    Get person-level health status from the reporting marts in a single
    round-trip: a one-row anchor LEFT JOINed to each mart, so missing
    rows degrade to NULLs. CCMS (score-run grain) and vaccinations
    (campaign grain) take the latest row per person.

    Args:
        person_id: Person identifier

    Returns:
        Single-row Series of prefixed columns, or None on failure
    """
    query = f"""
    SELECT
        brf.bmi_category                as brf_bmi_category,
        brf.bmi_value                   as brf_bmi_value,
        brf.smoking_status              as brf_smoking_status,
        brf.alcohol_status              as brf_alcohol_status,
        poly.medication_count           as poly_medication_count,
        poly.medication_count_band      as poly_medication_count_band,
        poly.is_polypharmacy_5plus      as poly_is_5plus,
        poly.is_polypharmacy_10plus     as poly_is_10plus,
        poly.polypharmacy_status_date   as poly_status_date,
        poly.medication_name_list       as poly_medication_name_list,
        bp.latest_bp_date               as bp_latest_date,
        bp.latest_systolic_value        as bp_systolic,
        bp.latest_diastolic_value       as bp_diastolic,
        bp.applied_patient_group        as bp_patient_group,
        bp.applied_systolic_threshold   as bp_systolic_threshold,
        bp.applied_diastolic_threshold  as bp_diastolic_threshold,
        bp.is_overall_bp_controlled     as bp_is_controlled,
        bp.hypertension_stage           as bp_hypertension_stage,
        bp.is_diagnosed_htn             as bp_is_diagnosed_htn,
        bp.recommended_monitoring_interval as bp_monitoring_interval,
        bp.is_latest_bp_within_recommended_interval as bp_within_interval,
        ccms.cambridge_comorbidity_score as ccms_score,
        ccms.last_updated               as ccms_last_updated,
        cerv.is_screening_eligible      as cerv_eligible,
        cerv.programme_status           as cerv_status,
        cerv.latest_completed_date      as cerv_last_completed,
        cerv.next_screening_due_date    as cerv_next_due,
        cerv.days_overdue               as cerv_days_overdue,
        bowel.is_screening_eligible     as bowel_eligible,
        bowel.programme_status          as bowel_status,
        bowel.latest_completed_date     as bowel_last_completed,
        bowel.next_screening_due_date   as bowel_next_due,
        bowel.days_overdue              as bowel_days_overdue,
        breast.is_screening_eligible    as breast_eligible,
        breast.programme_status         as breast_status,
        breast.latest_completed_date    as breast_last_completed,
        breast.next_screening_due_date  as breast_next_due,
        breast.days_overdue             as breast_days_overdue,
        pneumo.campaign                 as pneumo_campaign,
        pneumo.vaccination_status       as pneumo_status,
        pneumo.vaccination_date         as pneumo_date,
        rsv.eligible                    as rsv_eligible,
        rsv.campaign                    as rsv_campaign,
        rsv.vaccination_status          as rsv_status,
        rsv.vaccination_date            as rsv_date,
        shingles.eligible               as shingles_eligible,
        shingles.campaign               as shingles_campaign,
        shingles.vaccination_status     as shingles_status,
        shingles.vaccination_date       as shingles_date
    FROM (SELECT ? as person_id) k
    LEFT JOIN {TABLE_RISK_FACTORS} brf
        ON brf.person_id = k.person_id
    LEFT JOIN {TABLE_POLYPHARMACY} poly
        ON poly.person_id = k.person_id
    LEFT JOIN {TABLE_BP_CONTROL} bp
        ON bp.person_id = k.person_id
    LEFT JOIN (
        SELECT person_id, cambridge_comorbidity_score, last_updated
        FROM {TABLE_CCMS}
        WHERE person_id = ?
        QUALIFY ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY last_updated DESC) = 1
    ) ccms ON ccms.person_id = k.person_id
    LEFT JOIN {TABLE_CERVICAL_SCREENING} cerv
        ON cerv.person_id = k.person_id
    LEFT JOIN {TABLE_BOWEL_SCREENING} bowel
        ON bowel.person_id = k.person_id
    LEFT JOIN {TABLE_BREAST_SCREENING} breast
        ON breast.person_id = k.person_id
    LEFT JOIN (
        SELECT person_id, campaign, vaccination_status, vaccination_date
        FROM {TABLE_PNEUMOCOCCAL}
        WHERE person_id = ?
        QUALIFY ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY campaign DESC) = 1
    ) pneumo ON pneumo.person_id = k.person_id
    LEFT JOIN (
        SELECT person_id, eligible, campaign, vaccination_status, vaccination_date
        FROM {TABLE_RSV}
        WHERE person_id = ?
        QUALIFY ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY campaign DESC) = 1
    ) rsv ON rsv.person_id = k.person_id
    LEFT JOIN (
        SELECT person_id, eligible, campaign, vaccination_status, vaccination_date
        FROM {TABLE_SHINGLES}
        WHERE person_id = ?
        QUALIFY ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY campaign DESC) = 1
    ) shingles ON shingles.person_id = k.person_id
    """

    try:
        pid = int(person_id)
        result = run_query(query, [pid, pid, pid, pid, pid])
        if result.empty:
            return None
        return result.iloc[0]
    except Exception as e:
        st.warning(f"Could not load health status: {str(e)}")
        return None
