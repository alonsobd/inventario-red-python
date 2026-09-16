import sqlite3

import pandas as pd
import streamlit as st

DB_NAME = "inventario.db"

st.set_page_config(page_title="Inventario de Red", layout="wide")
st.title("Inventario de Red")

with sqlite3.connect(DB_NAME) as conexion:
    escaneos = pd.read_sql_query(
        """
        SELECT id, fecha, interfaz, red, duracion_segundos
        FROM escaneos
        ORDER BY id DESC
        """,
        conexion,
    )

    dispositivos = pd.read_sql_query(
        """
        SELECT escaneo_id, ip, hostname, mac, fabricante
        FROM dispositivos
        ORDER BY ip
        """,
        conexion,
    )

if escaneos.empty:
    st.warning("Todavía no hay escaneos guardados.")
    st.stop()

ultimo = escaneos.iloc[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Último escaneo", ultimo["fecha"])
col2.metric("Interfaz", ultimo["interfaz"])
col3.metric("Red", ultimo["red"])
col4.metric("Duración", f"{ultimo['duracion_segundos']} s")

st.subheader("Historial de escaneos")
st.dataframe(escaneos, use_container_width=True)

st.subheader("Dispositivos detectados")
st.dataframe(dispositivos, use_container_width=True)

if not dispositivos.empty:
    fabricantes = dispositivos["fabricante"].value_counts()
    st.subheader("Fabricantes")
    st.bar_chart(fabricantes)
