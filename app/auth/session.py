import streamlit as st


SESSION_USER_KEY = "__user__"


def require_login():
    if SESSION_USER_KEY not in st.session_state:
        st.switch_page("app/ui/streamlit_app.py")


def current_user():
    return st.session_state.get(SESSION_USER_KEY)
