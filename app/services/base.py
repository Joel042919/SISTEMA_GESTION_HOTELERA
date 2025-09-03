import functools
import streamlit as st
from app.auth.rbac import is_allowed


def policy_check(perm:str):
    def dec(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            user = st.session_state.get('__user__')
            if not user:
                st.error('No autenticado'); st.stop()
            roles = user.get('roles', [])
            if not is_allowed(roles, perm):
                st.error('Acceso denegado'); st.stop()
            return fn(*args, **kwargs)
        return wrapper
    return dec

