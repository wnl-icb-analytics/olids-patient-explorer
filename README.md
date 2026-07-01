# OLIDS Patient Record Explorer

Streamlit application for exploring individual patient records from OLIDS data, providing an EHR-style view of patient clinical records and demographics.

## Features

- **Patient Search**: Search by `sk_patient_id` (primary) or `person_id` with inline status badges
- **Patient Summary**: Overview including:
  - Record summary metrics (observations, medications, appointments) in a single query
  - Allergies & intolerances (always shown; separates 'No known allergy' records)
  - Core demographics (age, gender, ethnicity, life stage)
  - Registration history timeline with effective dates
  - Geographic information (borough, deprivation indices, LSOA, ward)
  - Language and interpreter requirements
  - Long-term conditions summary
  - Health status & prevention: risk factors (BMI/smoking/alcohol), blood pressure
    control (NG136), polypharmacy, screening programmes, vaccinations,
    Cambridge Comorbidity Score
  - Problems (Active & Past) - loaded on demand
- **Observations**: Date range filtering, SNOMED code/description search, problem
  flag and episodicity, values with units
- **Medications**: Current and Past sections with status derivation from
  statement/order joins
- **Appointments**: Upcoming and past with timeline charts by status and slot category
- **Referrals**: Referral reason, priority, type, mode and direction
- **Procedures**: Procedure requests with status

Records flagged `is_confidential` in the source are marked with 🔒.
Query results are cached (10 min TTL) and all user input is bound as query
parameters.

## Project Structure

```
olids-patient-explorer/
├── streamlit_app.py              # Main entry point
├── config.py                     # Database config & constants
├── database.py                   # Snowflake connection
├── environment.yml               # Conda dependencies
│
├── services/                     # Data access layer
│   ├── patient_service.py        # Patient search & demographics
│   ├── record_service.py         # Observations, medications, appointments,
│   │                             # problems, allergies, referrals, procedures
│   └── status_service.py         # Health status marts (reporting layer)
│
├── page_modules/                 # Page implementations
│   ├── search.py                 # Patient search page
│   ├── patient_summary.py        # Patient summary/dashboard
│   ├── observations.py           # Observations view
│   ├── medications.py            # Medications view (Current/Past)
│   ├── appointments.py           # Appointments view with charts
│   ├── referrals.py              # Referrals view
│   └── procedures.py             # Procedure requests view
│
└── utils/                        # Helper functions
    └── helpers.py                # Formatting utilities
```

## Database Schema

### Tables Used

**Staging Tables** (`STAGING.OLIDS`):
- `STG_OLIDS_OBSERVATION`: Patient observations with problem flags and episodicity
- `STG_OLIDS_MEDICATION_ORDER`: Medication orders with `issue_method_description`
- `STG_OLIDS_MEDICATION_STATEMENT`: Medication statements with `authorisation_type_display`
- `STG_OLIDS_APPOINTMENT`: Appointment records
- `STG_OLIDS_APPOINTMENT_PRACTITIONER`: Appointment-practitioner relationships
- `STG_OLIDS_ALLERGY_INTOLERANCE`: Allergies and intolerances
- `STG_OLIDS_REFERRAL_REQUEST`: Referral requests
- `STG_OLIDS_PROCEDURE_REQUEST`: Procedure requests
- `STG_OLIDS_PRACTITIONER`: Practitioner information
- `STG_OLIDS_CONCEPT`: Concept definitions

Not surfaced: `STG_OLIDS_DIAGNOSTIC_ORDER` (empty in source),
`STG_OLIDS_ENCOUNTER` (type/sub_type unpopulated; concept labels dominated by
EMIS migration placeholders).

**Demographics Tables** (`REPORTING.OLIDS_PERSON_DEMOGRAPHICS`):
- `DIM_PERSON_DEMOGRAPHICS`: Current patient demographics
- `DIM_PERSON_DEMOGRAPHICS_HISTORICAL`: Historical demographic changes (SCD-2)

**Disease Registers** (`REPORTING.OLIDS_DISEASE_REGISTERS`):
- `FCT_PERSON_LTC_SUMMARY`: Long-term conditions summary (long format - new
  registers appear as rows, no app change needed)

**Health Status Marts** (one row per person):
- `REPORTING.OLIDS_PERSON_STATUS`: `FCT_PERSON_BEHAVIOURAL_RISK_FACTORS`, `FCT_PERSON_POLYPHARMACY_CURRENT`
- `REPORTING.OLIDS_MEASURES`: `FCT_PERSON_BP_CONTROL`
- `REPORTING.OLIDS_RISK_STRATIFICATION`: `DIM_PERSON_CCMS`
- `REPORTING.OLIDS_PROGRAMME`: cervical/bowel/breast screening status,
  pneumococcal/RSV/shingles vaccination status

The staging tables mirror the source data but have data quality tests and deduplication applied.

## Deployment

This application is designed to run on Snowflake's Streamlit platform.

### Requirements

- Python 3.11
- Snowflake Snowpark Python
- Streamlit

### Environment Setup

```bash
conda env create -f environment.yml
conda activate app_environment
```

### Running Locally

```bash
streamlit run streamlit_app.py
```

## Configuration

Database connection and configuration settings are managed in `config.py`. The application uses:

- **Role**: `ENGINEER`
- **Warehouse**: `WH_NCL_ENGINEERING_XS`
- **Schemas**:
  - `STAGING.OLIDS` for staging clinical data
  - `REPORTING.OLIDS_PERSON_DEMOGRAPHICS` for demographics
  - `REPORTING.OLIDS_DISEASE_REGISTERS` for long-term conditions

## Privacy Considerations

This application includes OLIDS data. Do not publish or share outputs without DAC approval.

## License

Internal use only - NCL ICB Analytics
