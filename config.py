"""
Configuration settings for OLIDS Patient Record Explorer
"""

# Database configuration
# OLIDS staging models materialize in STAGING.OLIDS (post-2026 schema realignment;
# was MODELLING.DBT_STAGING)
DB_STAGING = "STAGING.OLIDS"
DB_DEMOGRAPHICS = "REPORTING.OLIDS_PERSON_DEMOGRAPHICS"
DB_DISEASE_REGISTERS = "REPORTING.OLIDS_DISEASE_REGISTERS"
DB_PERSON_STATUS = "REPORTING.OLIDS_PERSON_STATUS"
DB_MEASURES = "REPORTING.OLIDS_MEASURES"
DB_PROGRAMME = "REPORTING.OLIDS_PROGRAMME"
DB_RISK_STRATIFICATION = "REPORTING.OLIDS_RISK_STRATIFICATION"

# Table names
TABLE_OBSERVATION = f"{DB_STAGING}.STG_OLIDS_OBSERVATION"
TABLE_PERSON = f"{DB_STAGING}.STG_OLIDS_PERSON"
TABLE_MEDICATION_ORDER = f"{DB_STAGING}.STG_OLIDS_MEDICATION_ORDER"
TABLE_MEDICATION_STATEMENT = f"{DB_STAGING}.STG_OLIDS_MEDICATION_STATEMENT"
TABLE_PRACTITIONER = f"{DB_STAGING}.STG_OLIDS_PRACTITIONER"
TABLE_DIM_PERSON = f"{DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS"
TABLE_DIM_PERSON_HISTORICAL = f"{DB_DEMOGRAPHICS}.DIM_PERSON_DEMOGRAPHICS_HISTORICAL"
TABLE_LTC_SUMMARY = f"{DB_DISEASE_REGISTERS}.FCT_PERSON_LTC_SUMMARY"
TABLE_APPOINTMENT = f"{DB_STAGING}.STG_OLIDS_APPOINTMENT"
TABLE_APPOINTMENT_PRACTITIONER = f"{DB_STAGING}.STG_OLIDS_APPOINTMENT_PRACTITIONER"
TABLE_CONCEPT = f"{DB_STAGING}.STG_OLIDS_CONCEPT"
TABLE_CONCEPT_MAP = f"{DB_STAGING}.STG_OLIDS_CONCEPT_MAP"
TABLE_ALLERGY = f"{DB_STAGING}.STG_OLIDS_ALLERGY_INTOLERANCE"
TABLE_REFERRAL = f"{DB_STAGING}.STG_OLIDS_REFERRAL_REQUEST"
TABLE_ORGANISATION = f"{DB_STAGING}.STG_OLIDS_ORGANISATION"
TABLE_PROCEDURE_REQUEST = f"{DB_STAGING}.STG_OLIDS_PROCEDURE_REQUEST"

# Person-level analytics marts (one row per person unless noted)
TABLE_RISK_FACTORS = f"{DB_PERSON_STATUS}.FCT_PERSON_BEHAVIOURAL_RISK_FACTORS"
TABLE_POLYPHARMACY = f"{DB_PERSON_STATUS}.FCT_PERSON_POLYPHARMACY_CURRENT"
TABLE_BP_CONTROL = f"{DB_MEASURES}.FCT_PERSON_BP_CONTROL"
TABLE_CCMS = f"{DB_RISK_STRATIFICATION}.DIM_PERSON_CCMS"
TABLE_CERVICAL_SCREENING = f"{DB_PROGRAMME}.FCT_CERVICAL_SCREENING_STATUS"
TABLE_BOWEL_SCREENING = f"{DB_PROGRAMME}.FCT_BOWEL_SCREENING_STATUS"
TABLE_BREAST_SCREENING = f"{DB_PROGRAMME}.FCT_BREAST_SCREENING_STATUS"
TABLE_PNEUMOCOCCAL = f"{DB_PROGRAMME}.FCT_PNEUMOCOCCAL_VACCINATION_STATUS"
TABLE_RSV = f"{DB_PROGRAMME}.FCT_RSV_VACCINATION_STATUS"
TABLE_SHINGLES = f"{DB_PROGRAMME}.FCT_SHINGLES_VACCINATION_STATUS"

# Snowflake configuration
ROLE = "ENGINEER"
WAREHOUSE = "WH_NCL_ENGINEERING_XS"

# Page configuration
PAGE_CONFIG = {
    "page_title": "OLIDS Patient Record Explorer",
    "page_icon": "📋",
    "layout": "wide",
    "initial_sidebar_state": "collapsed"
}

# Query limits
MAX_OBSERVATIONS = 10000

# Query result cache lifetime (seconds). Source data refreshes daily, so this
# only bounds staleness within a session.
CACHE_TTL = 600

# Date range filter options
DATE_RANGE_OPTIONS = {
    "Last 12 months": 365,
    "All time": None
}

# Date range options for past medications
PAST_MEDICATIONS_DATE_RANGE_OPTIONS = {
    "90 days": 90,
    "1 year": 365,
    "All": None
}

# Custom CSS for styling
CUSTOM_CSS = """
<style>
    /* Status badges */
    .status-active {
        background-color: #28a745;
        color: #ffffff;
        padding: 6px 16px;
        border-radius: 6px;
        font-weight: 600;
        display: inline-block;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        vertical-align: middle;
    }

    .status-inactive {
        background-color: #dc3545;
        color: #ffffff;
        padding: 6px 16px;
        border-radius: 6px;
        font-weight: 600;
        display: inline-block;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        vertical-align: middle;
    }

    .status-deceased {
        background-color: #6c757d;
        color: #ffffff;
        padding: 6px 16px;
        border-radius: 6px;
        font-weight: 600;
        display: inline-block;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        vertical-align: middle;
    }

    /* Demographics grid */
    .demo-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 16px;
        margin-top: 16px;
    }

    .demo-item {
        background-color: #ffffff;
        padding: 12px;
        border-radius: 6px;
        border: 1px solid #dee2e6;
    }

    .demo-label {
        font-size: 0.85rem;
        color: #6c757d;
        font-weight: 600;
        margin-bottom: 4px;
    }

    .demo-value {
        font-size: 1rem;
        color: #212529;
    }

    /* Search box styling */
    .search-container {
        max-width: 600px;
        margin: 40px auto;
    }

    /* Reduce spacing before search form */
    .search-container p {
        margin-bottom: 0.5rem;
    }

    /* Hide form border, padding, and margin */
    [data-testid="stForm"] {
        border: 0px;
        padding: 0px;
        margin-top: 0px;
    }

    /* Remove spacing from element containers in forms */
    [data-testid="stForm"] > [data-testid="stElementContainer"] {
        margin-top: 0px;
        padding-top: 0px;
    }

    /* Metric cards */
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        padding: 16px;
        border-radius: 8px;
    }
    /* Condition badges */
    .condition-badge {
        display: inline-block;
        padding: 8px 12px;
        margin: 4px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 500;
    }

    .condition-qof {
        background-color: #cfe2ff;
        color: #084298;
        border: 1px solid #9ec5fe;
    }

    .condition-other {
        background-color: #f8f9fa;
        color: #495057;
        border: 1px solid #dee2e6;
    }
</style>
"""
