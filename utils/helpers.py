"""
Helper functions for formatting and display
"""

from datetime import datetime
import streamlit as st


def format_date(date_value):
    """
    Format date value for display.

    Args:
        date_value: Date value (datetime, date, or string)

    Returns:
        Formatted date string or 'N/A'
    """
    if date_value is None:
        return "N/A"

    try:
        if isinstance(date_value, str):
            # Try to parse string date
            date_value = datetime.strptime(date_value, "%Y-%m-%d")

        return date_value.strftime("%d %b %Y")
    except:
        return str(date_value)


def format_boolean(value):
    """
    Format boolean value with emoji.

    Args:
        value: Boolean value

    Returns:
        Formatted string with emoji
    """
    if value is None:
        return "N/A"
    return "Yes" if value else "No"


def render_status_badge(is_active, is_deceased, inactive_reason=None):
    """
    Render status badge for patient.

    Args:
        is_active: Active registration status
        is_deceased: Deceased status
        inactive_reason: Reason for inactive status
    """
    if is_deceased:
        st.markdown('<span class="status-deceased">DECEASED</span>', unsafe_allow_html=True)
    elif is_active:
        st.markdown('<span class="status-active">ACTIVE</span>', unsafe_allow_html=True)
    else:
        reason = f" - {inactive_reason}" if inactive_reason else ""
        st.markdown(f'<span class="status-inactive">INACTIVE{reason}</span>', unsafe_allow_html=True)




def get_status_badge_html(is_active, is_deceased, inactive_reason=None):
    """
    Get status badge HTML for inline display.

    Args:
        is_active: Active registration status
        is_deceased: Deceased status
        inactive_reason: Reason for inactive status

    Returns:
        HTML string for badge
    """
    if is_deceased:
        return '<span class="status-deceased">DECEASED</span>'
    elif is_active:
        return '<span class="status-active">ACTIVE</span>'
    else:
        reason = f" - {inactive_reason}" if inactive_reason else ""
        return f'<span class="status-inactive">INACTIVE{reason}</span>'


def format_value_with_unit(value, unit):
    """
    Format observation value with unit.

    Args:
        value: Observation value
        unit: Unit of measurement

    Returns:
        Formatted string
    """
    if value is None or value == "":
        return "N/A"

    if unit and unit != "":
        return f"{value} {unit}"

    return str(value)


def safe_str(value):
    """
    Safely convert value to string.

    Args:
        value: Any value

    Returns:
        String representation or 'N/A'
    """
    if value is None or value == "":
        return "N/A"
    return str(value)


def format_practitioner_name(last_name, first_name, title, role=None):
    """
    Format practitioner name as: LAST_NAME, First_Name (Title) · Role

    Args:
        last_name: Practitioner last name
        first_name: Practitioner first name
        title: Practitioner title
        role: Practitioner role from practitioner_in_role (optional)

    Returns:
        Formatted name string or 'N/A'
    """
    if not last_name or last_name == "N/A":
        return "N/A"

    # Format: LAST_NAME, First_Name
    name_parts = []
    if last_name:
        name_parts.append(last_name.upper())
    if first_name and first_name != "N/A":
        first_formatted = first_name.capitalize() if first_name else ""
        name_parts.append(first_formatted)

    name = ", ".join(name_parts) if len(name_parts) > 1 else (name_parts[0] if name_parts else "N/A")

    # Add title if present
    if title and title != "N/A":
        name = f"{name} ({title})"

    # Add role if present (isinstance guards against NaN)
    if isinstance(role, str) and role and role != "N/A":
        name = f"{name} · {role}"

    return name

def format_month_year(date_value):
    """
    Format date as month and year only (e.g., "Aug 1967").

    Args:
        date_value: Date value (datetime, date, or string)

    Returns:
        Formatted date string as "MMM YYYY" or 'N/A'
    """
    if date_value is None:
        return "N/A"

    try:
        if isinstance(date_value, str):
            date_value = datetime.strptime(date_value, "%Y-%m-%d")

        return date_value.strftime("%b %Y")
    except:
        return str(date_value)
