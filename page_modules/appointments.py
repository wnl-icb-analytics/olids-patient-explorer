"""
Appointments view page
"""

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from services.record_service import get_patient_appointments, calculate_date_range
from utils.helpers import format_date, safe_str, format_practitioner_name
from config import DATE_RANGE_OPTIONS


def render_appointments():
    """
    Render the appointments view page with visualization and table.
    """
    # Check if patient is selected
    if "selected_patient" not in st.session_state or not st.session_state.selected_patient:
        st.warning("No patient selected. Please search for a patient first.")
        if st.button("Back to Search"):
            st.session_state.page = "search"
            st.rerun()
        return

    sk_patient_id = st.session_state.selected_patient

    # Resolve person_id for record queries
    from services.patient_service import get_person_id
    person_id = get_person_id(sk_patient_id)
    if person_id is None:
        st.error("Failed to resolve patient identifier")
        return

    # Navigation buttons
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("← Back to Summary"):
            st.session_state.page = "patient_summary"
            st.rerun()
    with col2:
        if st.button("← Back to Search"):
            st.session_state.page = "search"
            st.session_state.search_results = None
            st.rerun()

    st.markdown(f"## Appointments for Patient: {sk_patient_id}")

    # Load all appointments (future appointments always shown, no date filter)
    with st.spinner("Loading appointments..."):
        appointments = get_patient_appointments(person_id, date_from=None, date_to=None, include_future=True)

    if appointments.empty:
        st.info("No appointments found")
    else:
        # Prepare display dataframe
        display_df = appointments.copy()
        
        # Convert start_date to datetime
        display_df["START_DATE"] = pd.to_datetime(display_df["START_DATE"])
        
        # Separate future and past appointments
        future_df = display_df[display_df["IS_FUTURE"] == True].copy()
        past_df = display_df[display_df["IS_FUTURE"] == False].copy()
        
        # Always show future appointments section
        st.markdown("### 📅 Upcoming Appointments")
        if not future_df.empty:
            st.markdown(f"**{len(future_df)} upcoming appointment(s)**")
            render_appointment_table(future_df, show_charts=False)
        else:
            st.markdown("No future appointments booked")
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Past appointments section
        if not past_df.empty:
            st.markdown("### 📊 Past Appointments")
            
            # Date range filter for past appointments
            date_range = st.selectbox(
                "Date Range",
                options=list(DATE_RANGE_OPTIONS.keys()),
                index=0,
                key="past_appointments_date_range"
            )
            
            # Calculate date range
            date_from, date_to = calculate_date_range(date_range)
            
            # Filter past appointments by date range
            if date_from:
                past_df = past_df[past_df["START_DATE"] >= pd.to_datetime(date_from)]
            if date_to:
                past_df = past_df[past_df["START_DATE"] <= pd.to_datetime(date_to)]
            
            if past_df.empty:
                st.info("No past appointments found for the selected time period")
                return
            
            st.markdown(f"**Showing {len(past_df):,} past appointment(s)** (limited to 10,000 most recent)")
            
            # Create year-month for grouping (format: yyyy-mmm)
            past_df["YEAR_MONTH"] = past_df["START_DATE"].dt.strftime("%Y-%b")
            
            # Clean up status names
            past_df["STATUS_DISPLAY"] = past_df["APPOINTMENT_STATUS"].apply(
                lambda x: safe_str(x).title() if pd.notna(x) else "Unknown"
            )
            
            # Clean up slot category names
            past_df["SLOT_CATEGORY"] = past_df["NATIONAL_SLOT_CATEGORY_NAME"].apply(
                lambda x: safe_str(x) if x and x != "N/A" else "Not Specified"
            )
            
            # Visualization Section
            st.markdown("#### Trends")
            
            # Determine date range for placeholder months
            if date_from and date_to:
                # Use selected date range
                chart_start = pd.to_datetime(date_from).to_period("M").to_timestamp()
                chart_end = pd.to_datetime(date_to).to_period("M").to_timestamp()
            elif date_from:
                # Use date_from to today
                chart_start = pd.to_datetime(date_from).to_period("M").to_timestamp()
                chart_end = pd.to_datetime(datetime.now()).to_period("M").to_timestamp()
            else:
                # Use data range
                chart_start = past_df["START_DATE"].min().to_period("M").to_timestamp()
                chart_end = past_df["START_DATE"].max().to_period("M").to_timestamp()
            
            # Generate all months in range
            all_months = []
            current = chart_start
            while current <= chart_end:
                year_month = current.strftime("%Y-%b")
                all_months.append({
                    'YEAR_MONTH': year_month,
                    'SORT_DATE': current
                })
                # Move to next month
                current = (current.to_period("M") + 1).to_timestamp()
            
            all_months_df = pd.DataFrame(all_months)
            
            # Create sortable date column
            past_df["SORT_DATE"] = past_df["START_DATE"].dt.to_period("M").dt.to_timestamp()
            
            # Get all unique statuses and slot categories
            all_statuses = past_df["STATUS_DISPLAY"].unique()
            all_slot_categories = past_df["SLOT_CATEGORY"].unique()
            
            # Group by month and status
            status_counts = past_df.groupby(["YEAR_MONTH", "STATUS_DISPLAY", "SORT_DATE"]).size().reset_index(name="COUNT")
            
            # Create complete status counts with placeholder months
            status_complete = []
            for _, month_row in all_months_df.iterrows():
                for status in all_statuses:
                    matching = status_counts[
                        (status_counts["YEAR_MONTH"] == month_row["YEAR_MONTH"]) &
                        (status_counts["STATUS_DISPLAY"] == status)
                    ]
                    count = matching["COUNT"].iloc[0] if not matching.empty else 0
                    status_complete.append({
                        'YEAR_MONTH': month_row["YEAR_MONTH"],
                        'STATUS_DISPLAY': status,
                        'SORT_DATE': month_row["SORT_DATE"],
                        'COUNT': count
                    })
            
            status_counts_complete = pd.DataFrame(status_complete)
            status_counts_complete = status_counts_complete.sort_values("SORT_DATE")
            
            # Create timeline chart colored by status using Altair
            status_chart = alt.Chart(status_counts_complete).mark_bar().encode(
                x=alt.X("YEAR_MONTH:N", title="Month", axis=alt.Axis(labelAngle=-45), sort=alt.SortField(field="SORT_DATE", order="ascending")),
                y=alt.Y("COUNT:Q", title="Number of Appointments"),
                color=alt.Color("STATUS_DISPLAY:N", title="Status", legend=alt.Legend(columns=1, symbolLimit=0, labelLimit=250)),
                tooltip=["YEAR_MONTH:N", "STATUS_DISPLAY:N", "COUNT:Q"]
            ).properties(
                title="Appointments Over Time by Status",
                width="container",
                height=400
            ).configure_legend(
                padding=15,
                labelLimit=250
            )
            st.altair_chart(status_chart, use_container_width=True)
            
            # Second chart: by slot category
            slot_counts = past_df.groupby(["YEAR_MONTH", "SLOT_CATEGORY", "SORT_DATE"]).size().reset_index(name="COUNT")
            
            # Create complete slot counts with placeholder months
            slot_complete = []
            for _, month_row in all_months_df.iterrows():
                for category in all_slot_categories:
                    matching = slot_counts[
                        (slot_counts["YEAR_MONTH"] == month_row["YEAR_MONTH"]) &
                        (slot_counts["SLOT_CATEGORY"] == category)
                    ]
                    count = matching["COUNT"].iloc[0] if not matching.empty else 0
                    slot_complete.append({
                        'YEAR_MONTH': month_row["YEAR_MONTH"],
                        'SLOT_CATEGORY': category,
                        'SORT_DATE': month_row["SORT_DATE"],
                        'COUNT': count
                    })
            
            slot_counts_complete = pd.DataFrame(slot_complete)
            slot_counts_complete = slot_counts_complete.sort_values("SORT_DATE")
            
            slot_chart = alt.Chart(slot_counts_complete).mark_bar().encode(
                x=alt.X("YEAR_MONTH:N", title="Month", axis=alt.Axis(labelAngle=-45), sort=alt.SortField(field="SORT_DATE", order="ascending")),
                y=alt.Y("COUNT:Q", title="Number of Appointments"),
                color=alt.Color("SLOT_CATEGORY:N", title="Slot Category", legend=alt.Legend(columns=1, symbolLimit=0, labelLimit=250)),
                tooltip=["YEAR_MONTH:N", "SLOT_CATEGORY:N", "COUNT:Q"]
            ).properties(
                title="Appointments Over Time by Slot Category",
                width="container",
                height=400
            ).configure_legend(
                padding=15,
                labelLimit=250
            )
            st.altair_chart(slot_chart, use_container_width=True)
            
            st.markdown("#### Details")
            render_appointment_table(past_df, show_charts=False)
        else:
            st.info("No past appointments found")


def render_appointment_table(df, show_charts=True):
    """
    Render appointment details table.
    
    Args:
        df: DataFrame with appointment data
        show_charts: Whether to show charts (not used currently)
    """
    # Format for table display
    df["DATE_DISPLAY"] = df["START_DATE"].apply(
        lambda x: x.strftime("%d %b %Y %H:%M") if pd.notna(x) else "N/A"
    )
    
    # Format status
    df["STATUS_DISPLAY"] = df["APPOINTMENT_STATUS"].apply(
        lambda x: safe_str(x).title() if pd.notna(x) else "Unknown"
    )
    
    # Format contact mode
    df["CONTACT_DISPLAY"] = df["CONTACT_MODE"].apply(
        lambda x: safe_str(x).replace("-", " ").title() if pd.notna(x) else "Not Specified"
    )
    
    # Format slot category
    df["SLOT_DISPLAY"] = df["NATIONAL_SLOT_CATEGORY_NAME"].apply(
        lambda x: safe_str(x) if x and x != "N/A" else "Not Specified"
    )
    
    # Format practitioner name
    df["PRACTITIONER"] = df.apply(
        lambda row: format_practitioner_name(
            row["PRACTITIONER_LAST_NAME"],
            row["PRACTITIONER_FIRST_NAME"],
            row["PRACTITIONER_TITLE"],
            row["PRACTITIONER_ROLE"]
        ),
        axis=1
    )
    
    # Format duration
    df["DURATION"] = df["PLANNED_DURATION"].apply(
        lambda x: f"{int(x)} min" if pd.notna(x) else "N/A"
    )
    
    # Select and rename columns for display
    table_df = df[[
        "DATE_DISPLAY",
        "STATUS_DISPLAY",
        "SLOT_DISPLAY",
        "CONTACT_DISPLAY",
        "DURATION",
        "PRACTITIONER"
    ]]
    table_df.columns = ["Date & Time", "Status", "Slot Category", "Contact Mode", "Duration", "Practitioner"]
    
    # Display table
    if len(df) > 10:
        st.dataframe(
            table_df,
            use_container_width=True,
            hide_index=True,
            height=600
        )
    else:
        st.dataframe(
            table_df,
            use_container_width=True,
            hide_index=True
        )
