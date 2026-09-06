import streamlit as st
from supabase import create_client

def supabase_config():
    SUPABASE_URL = st.secrets["supabase"]["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["supabase"]["SUPABASE_KEY"]
    return create_client(SUPABASE_URL, SUPABASE_KEY)
