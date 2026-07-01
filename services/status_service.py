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
    DB_OBSERVATIONS,
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
        efi.latest_efi_score_preferred  as efi_score,
        efi.latest_efi_category_preferred as efi_category,
        efi.latest_efi_date             as efi_date,
        rock.rockwood_score             as rockwood_score,
        rock.rockwood_description       as rockwood_description,
        waist.waist_circumference_value as waist_value,
        waist.waist_risk_category       as waist_category,
        audit.audit_score               as audit_score,
        audit.audit_type                as audit_type,
        audit.risk_category             as audit_risk_category,
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
    LEFT JOIN {DB_OBSERVATIONS}.INT_EFI_LATEST efi
        ON efi.person_id = k.person_id
    LEFT JOIN {DB_OBSERVATIONS}.INT_ROCKWOOD_LATEST rock
        ON rock.person_id = k.person_id
    LEFT JOIN {DB_OBSERVATIONS}.INT_WAIST_CIRCUMFERENCE_LATEST waist
        ON waist.person_id = k.person_id
    LEFT JOIN (
        SELECT person_id, audit_score, audit_type, risk_category
        FROM {DB_OBSERVATIONS}.INT_ALCOHOL_AUDIT_SCORES
        WHERE person_id = ?
            AND is_valid_score
        QUALIFY ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY clinical_effective_date DESC) = 1
    ) audit ON audit.person_id = k.person_id
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
        # Binds in query order: anchor, ccms, audit, pneumo, rsv, shingles
        result = run_query(query, [pid, pid, pid, pid, pid, pid])
        if result.empty:
            return None
        return result.iloc[0]
    except Exception as e:
        st.warning(f"Could not load health status: {str(e)}")
        return None


def get_person_biomarkers(person_id):
    """
    Get latest key results from the curated biomarker models
    (MODELLING.OLIDS_OBSERVATIONS INT_*_LATEST - one row per person,
    unit-standardised) in a single round-trip.

    Args:
        person_id: Person identifier

    Returns:
        Single-row Series of prefixed columns, or None on failure
    """
    query = f"""
    SELECT
        hba1c.hba1c_display                 as hba1c_value,
        hba1c.hba1c_category                as hba1c_category,
        hba1c.clinical_effective_date       as hba1c_date,
        chol.cholesterol_value              as chol_value,
        chol.cholesterol_category           as chol_category,
        chol.clinical_effective_date        as chol_date,
        ldl.cholesterol_value               as ldl_value,
        ldl.ldl_cvd_target_met              as ldl_target_met,
        ldl.clinical_effective_date         as ldl_date,
        egfr.egfr_value                     as egfr_value,
        egfr.ckd_stage                      as egfr_ckd_stage,
        egfr.clinical_effective_date        as egfr_date,
        creat.creatinine_value              as creatinine_value,
        creat.creatinine_category           as creatinine_category,
        creat.clinical_effective_date       as creatinine_date,
        acr.acr_value                       as acr_value,
        acr.acr_category                    as acr_category,
        acr.clinical_effective_date         as acr_date,
        hb.inferred_value                   as hb_value,
        hb.inferred_unit                    as hb_unit,
        hb.haemoglobin_category             as hb_category,
        hb.clinical_effective_date          as hb_date,
        plt.inferred_value                  as platelets_value,
        plt.inferred_unit                   as platelets_unit,
        plt.platelets_category              as platelets_category,
        plt.clinical_effective_date         as platelets_date,
        eos.inferred_value                  as eos_value,
        eos.inferred_unit                   as eos_unit,
        eos.eosinophil_category             as eos_category,
        eos.clinical_effective_date         as eos_date,
        lft.alt_value                       as alt_value,
        lft.is_high_alt                     as alt_is_high,
        lft.alt_date                        as alt_date,
        lft.ggt_value                       as ggt_value,
        lft.is_high_ggt                     as ggt_is_high,
        lft.ggt_date                        as ggt_date,
        lft.bilirubin_value                 as bilirubin_value,
        lft.is_high_bilirubin               as bilirubin_is_high,
        lft.bilirubin_date                  as bilirubin_date,
        ckd.latest_ckd_stage_inferred       as ckd_stage_inferred,
        ckd.has_confirmed_ckd_by_labs       as ckd_confirmed,
        ckd.latest_labs_meet_ckd_criteria   as ckd_meets_criteria,
        ckd.latest_egfr_date                as ckd_date,
        glucose.blood_glucose_display       as glucose_value,
        glucose.is_fasting                  as glucose_is_fasting,
        glucose.clinical_effective_date     as glucose_date,
        qrisk.qrisk_score                   as qrisk_score,
        qrisk.qrisk_type                    as qrisk_type,
        qrisk.cvd_risk_category             as qrisk_category,
        qrisk.clinical_effective_date       as qrisk_date
    FROM (SELECT ? as person_id) k
    LEFT JOIN {DB_OBSERVATIONS}.INT_HBA1C_LATEST hba1c
        ON hba1c.person_id = k.person_id
    LEFT JOIN {DB_OBSERVATIONS}.INT_CHOLESTEROL_LATEST chol
        ON chol.person_id = k.person_id
    LEFT JOIN {DB_OBSERVATIONS}.INT_CHOLESTEROL_LDL_LATEST ldl
        ON ldl.person_id = k.person_id
    LEFT JOIN {DB_OBSERVATIONS}.INT_EGFR_LATEST egfr
        ON egfr.person_id = k.person_id
    LEFT JOIN {DB_OBSERVATIONS}.INT_CREATININE_LATEST creat
        ON creat.person_id = k.person_id
    LEFT JOIN {DB_OBSERVATIONS}.INT_URINE_ACR_LATEST acr
        ON acr.person_id = k.person_id
    LEFT JOIN {DB_OBSERVATIONS}.INT_HAEMOGLOBIN_LATEST hb
        ON hb.person_id = k.person_id
    LEFT JOIN {DB_OBSERVATIONS}.INT_PLATELETS_LATEST plt
        ON plt.person_id = k.person_id
    LEFT JOIN {DB_OBSERVATIONS}.INT_EOSINOPHIL_COUNT_LATEST eos
        ON eos.person_id = k.person_id
    LEFT JOIN {DB_OBSERVATIONS}.INT_LFT_LATEST lft
        ON lft.person_id = k.person_id
    LEFT JOIN {DB_OBSERVATIONS}.INT_CKD_LAB_CLASSIFICATION ckd
        ON ckd.person_id = k.person_id
    LEFT JOIN {DB_OBSERVATIONS}.INT_BLOOD_GLUCOSE_LATEST glucose
        ON glucose.person_id = k.person_id
    LEFT JOIN {DB_OBSERVATIONS}.INT_QRISK_LATEST qrisk
        ON qrisk.person_id = k.person_id
    """

    try:
        result = run_query(query, [int(person_id)])
        if result.empty:
            return None
        return result.iloc[0]
    except Exception as e:
        st.warning(f"Could not load key results: {str(e)}")
        return None
