import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Gestión de Deudas - TEN",
    page_icon="📊",
    layout="wide"
)

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def init_connection():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    # Carga las credenciales desde los secretos de Streamlit Cloud
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

try:
    client = init_connection()
    # Abre tu hoja de cálculo por nombre (asegúrate de que el archivo se llame "TEN" o cámbialo aquí)
    sheet = client.open("TEN")
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

# --- FUNCIONES DE CARGA DE DATOS ---
def load_data(sheet_name):
    try:
        worksheet = sheet.worksheet(sheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.warning(f"No se pudo cargar la pestaña {sheet_name}: {e}")
        return pd.DataFrame()

# --- INTERFAZ PRINCIPAL ---
st.title("📊 Control de Deudas y Cartera - TEN")
st.markdown("---")

tab1, tab2 = st.tabs(["💰 Deudas por Cobrar", "📉 Deudas por Pagar"])

with tab1:
    st.subheader("Listado de Deudas por Cobrar")
    df_cobrar = load_data("DEUDAS_X_COBRAR")
    
    if not df_cobrar.empty:
        # Filtro rápido
        filtro_estado = st.selectbox("Filtrar por Estatus (Cobrar):", ["Todos"] + list(df_cobrar["ESTATUS"].unique()))
        if filtro_estado != "Todos":
            df_cobrar = df_cobrar[df_cobrar["ESTATUS"] == filtro_estado]
            
        st.dataframe(df_cobrar, use_container_width=True)
    else:
        st.info("La tabla 'DEUDAS_X_COBRAR' está vacía o no se encontró.")

with tab2:
    st.subheader("Listado de Deudas por Pagar")
    df_pagar = load_data("DEUDA_X_PAGAR")
    
    if not df_pagar.empty:
        filtro_estado_p = st.selectbox("Filtrar por Estatus (Pagar):", ["Todos"] + list(df_pagar["ESTATUS"].unique()))
        if filtro_estado_p != "Todos":
            df_pagar = df_pagar[df_pagar["ESTATUS"] == filtro_estado_p]
            
        st.dataframe(df_pagar, use_container_width=True)
    else:
        st.info("La tabla 'DEUDA_X_PAGAR' está vacía o no se encontró.")
