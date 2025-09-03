import streamlit as st
from datetime import date
import pandas as pd
import psycopg
from app.core.db import POOL
from app.auth.session import current_user


u = current_user();
if not u: st.stop()


st.header("Reportes y Exportación")
selected_date = st.date_input("Fecha", value=date.today())


#with psycopg.connect(POOL.conninfo) as conn:
    #df = pd.read_sql(
    #"SELECT c.posted_at::date AS fecha, c.concept,