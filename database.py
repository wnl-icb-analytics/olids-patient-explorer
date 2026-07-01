"""
Database connection and query execution for Snowflake
"""

import streamlit as st
from config import CACHE_TTL


@st.cache_resource
def get_connection():
    """
    Get Snowflake connection using Streamlit's native connection.
    Connection is cached for performance.

    Returns:
        Snowflake session object
    """
    try:
        from snowflake.snowpark.context import get_active_session
        return get_active_session()
    except Exception as e:
        st.error(f"Failed to connect to Snowflake: {str(e)}")
        st.stop()


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def run_query(query, params=None):
    """
    Execute SQL with optional bind parameters (?) and return a DataFrame.

    Results are cached keyed on (query, params); exceptions are not cached,
    so transient failures are retried on the next rerun.
    """
    return get_connection().sql(query, params=params).to_pandas()
