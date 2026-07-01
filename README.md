# OLIDS Patient Record Explorer

Streamlit application for exploring individual patient records from OLIDS data, providing an EHR-style view of patient clinical records and demographics.

## Features

- **Patient Search**: Universal search by `sk_patient_id` (primary) or `person_id` with inline status badges
- **Patient Summary**: Comprehensive overview including:
  - Record summary metrics (observations, medications, appointments)
  - Core demographics (age, gender, ethnicity, life stage)
  - Registration history timeline with effective dates
  - Geographic information (borough, deprivation indices, LSOA, ward)
  - Language and interpreter requirements
  - Long-term conditions summary
  - Problems (Active & Past) - lazy loaded
- **Observations**: Browse patient observations with:
  - Date range filtering (Last 12 months, All time)
  - SNOMED code or description search
  - Problem flag and episodicity display
  - Values with units, sorted by most recent first
- **Medications**: Split into Current and Past sections:
  - Current medications: All active medications (no date filter)
  - Past medications: Filtered by date range (90 days, 1 year, All)
  - Uses `issue_method_description` and `authorisation_type_display` from proper table joins
- **Appointments**: View appointments with:
  - Upcoming appointments (always shown)
  - Past appointments with date range filtering
  - Interactive timeline charts showing trends by status and slot category
  - Placeholder months for periods without activity

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
│   └── record_service.py         # Observations, medications, appointments, problems
│
├── page_modules/                 # Page implementations
│   ├── search.py                 # Patient search page
│   ├── patient_summary.py        # Patient summary/dashboard
│   ├── observations.py           # Observations view
│   ├── medications.py            # Medications view (Current/Past)
│   ├── appointments.py           # Appointments view with charts
│   └── patient_record.py         # Legacy record view
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
- `STG_OLIDS_PRACTITIONER`: Practitioner information
- `STG_OLIDS_CONCEPT`: Concept definitions
- `STG_OLIDS_CONCEPT_MAP`: Concept mappings for lookups

**Demographics Tables** (`REPORTING.OLIDS_PERSON_DEMOGRAPHICS`):
- `DIM_PERSON_DEMOGRAPHICS`: Current patient demographics
- `DIM_PERSON_DEMOGRAPHICS_HISTORICAL`: Historical demographic changes (SCD-2)

**Disease Registers** (`REPORTING.OLIDS_DISEASE_REGISTERS`):
- `FCT_PERSON_LTC_SUMMARY`: Long-term conditions summary

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

- **Role**: `APP_ADMIN`
- **Warehouse**: `WH_NCL_ENGINEERING_XS`
- **Schemas**:
  - `STAGING.OLIDS` for staging clinical data
  - `REPORTING.OLIDS_PERSON_DEMOGRAPHICS` for demographics
  - `REPORTING.OLIDS_DISEASE_REGISTERS` for long-term conditions

## Privacy Considerations

This application includes OLIDS data. Do not publish or share outputs without DAC approval.

## License

Internal use only - NCL ICB Analytics
