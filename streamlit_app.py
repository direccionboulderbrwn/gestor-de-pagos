import streamlit as st
import pandas as pd

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Gestión de Pagos - TEN",
    page_icon="📊",
    layout="wide"
)

# --- RUTA DEL ARCHIVO EXCEL EN GITHUB ---
EXCEL_FILE = "TEN.xlsx"  # Cambia esto por el nombre exacto de tu archivo subido a GitHub

# --- FUNCIÓN DE CARGA DE DATOS ---
@st.cache_data
def load_excel_data(file_path, sheet_name):
    try:
        # Lee la pestaña específica del archivo de Excel
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        return df
    except Exception as e:
        st.warning(f"No se pudo cargar la pestaña {sheet_name}: {e}")
        return pd.DataFrame()

# --- INTERFAZ PRINCIPAL ---
st.title("📊 Control de Deudas y Cartera - TEN")
st.markdown("---")

tab1, tab2 = st.tabs(["💰 Deudas por Cobrar", "📉 Deudas por Pagar"])

with tab1:
    st.subheader("Listado de Deudas por Cobrar")
    df_cobrar = load_excel_data(EXCEL_FILE, "DEUDAS_X_COBRAR")
    
    if not df_cobrar.empty:
        # Filtro rápido por Estatus si la columna existe
        if "ESTATUS" in df_cobrar.columns:
            filtro_estado = st.selectbox("Filtrar por Estatus (Cobrar):", ["Todos"] + list(df_cobrar["ESTATUS"].unique()))
            if filtro_estado != "Todos":
                df_cobrar = df_cobrar[df_cobrar["ESTATUS"] == filtro_estado]
                
        st.dataframe(df_cobrar, use_container_width=True)
    else:
        st.info("La pestaña 'DEUDAS_X_COBRAR' está vacía o no se encontró en el archivo Excel.")

with tab2:
    st.subheader("Listado de Deudas por Pagar")
    df_pagar = load_excel_data(EXCEL_FILE, "DEUDA_X_PAGAR")
    
    if not df_pagar.empty:
        if "ESTATUS" in df_pagar.columns:
            filtro_estado_p = st.selectbox("Filtrar por Estatus (Pagar):", ["Todos"] + list(df_pagar["ESTATUS"].unique()))
            if filtro_estado_p != "Todos":
                df_pagar = df_pagar[df_pagar["ESTATUS"] == filtro_estado_p]
                
        st.dataframe(df_pagar, use_container_width=True)
    else:
        st.info("La pestaña 'DEUDA_X_PAGAR' está vacía o no se encontró en el archivo Excel.")
