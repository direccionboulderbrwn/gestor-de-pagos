import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import uuid

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Gestión de Deudas y Cartera - TEN",
    page_icon="📊",
    layout="wide"
)

# --- INICIALIZAR CONEXIÓN CON SUPABASE ---
@st.cache_resource
def init_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase: Client = init_supabase()

# --- FUNCIÓN AUXILIAR PARA LEER TABLAS ---
def fetch_table(table_name):
    try:
        response = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error al cargar {table_name}: {e}")
        return pd.DataFrame()

# --- FUNCIÓN PARA GENERAR ID ÚNICO AUTOMÁTICO ---
def generar_id(prefijo="MOV"):
    # Genera un identificador único basado en timestamp y sufijo aleatorio corto
    sufijo = uuid.uuid4().hex[:6].upper()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefijo}-{timestamp}-{sufijo}"

# --- TÍTULO PRINCIPAL ---
st.title("📊 Control Operativo y Financiero - TEN")
st.markdown("---")

# Pestañas principales de navegación
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💰 Deudas por Cobrar", 
    "📉 Deudas por Pagar", 
    "📈 Balance Automático",
    "👥 Clientes y Proveedores",
    "⚠️ Penalizaciones"
])

# ==========================================
# TAB 1: DEUDAS POR COBRAR
# ==========================================
with tab1:
    st.subheader("Listado de Deudas por Cobrar")
    df_cobrar = fetch_table("DEUDAS_X_COBRAR")
    
    if not df_cobrar.empty:
        if "ESTATUS" in df_cobrar.columns:
            estatus_list = ["Todos"] + list(df_cobrar["ESTATUS"].dropna().unique())
            filtro = st.selectbox("Filtrar por Estatus:", estatus_list, key="filtro_cobrar")
            if filtro != "Todos":
                df_cobrar = df_cobrar[df_cobrar["ESTATUS"] == filtro]
                
        st.dataframe(df_cobrar, use_container_width=True)
    else:
        st.info("No hay registros en la tabla DEUDAS_X_COBRAR.")
        
    with st.expander("➕ Registrar Nueva Deuda por Cobrar"):
        # Generar ID automático único para esta sesión de formulario
        id_mov_auto = generar_id("CXC")
        
        with st.form("form_nueva_deuda_cobrar"):
            # ID visible pero no manipulable (disabled=True)
            st.text_input("ID Movimiento (Generado Automáticamente)", value=id_mov_auto, disabled=True)
            
            venta_gasto = st.selectbox("Tipo", ["Venta", "Gasto"])
            estatus = st.selectbox("Estatus", ["Pendiente", "Pagado", "Parcial"])
            valor = st.number_input("Valor ($)", min_value=0.0, format="%.2f")
            
            df_clientes = fetch_table("CLIENTES")
            lista_clientes = df_clientes["ID_CLIENTE"].tolist() if not df_clientes.empty else []
            cliente = st.selectbox("Cliente", lista_clientes)
            
            fecha_op = st.date_input("Fecha de Operación")
            concepto = st.text_area("Concepto / Detalle")
            
            submit_cobrar = st.form_submit_button("Guardar Deuda")
            
            if submit_cobrar:
                try:
                    data_cobrar = {
                        "ID_MOVIMIENTO": id_mov_auto,
                        "VENTA_GASTO": venta_gasto,
                        "ESTATUS": estatus,
                        "VALOR": valor,
                        "CLIENTE": cliente,
                        "FECHA_OPERACION": str(fecha_op),
                        "CONCEPTO": concepto
                    }
                    supabase.table("DEUDAS_X_COBRAR").insert(data_cobrar).execute()
                    
                    if estatus in ["Pagado", "Parcial"]:
                        data_balance = {
                            "ID_BALANCE": f"BAL-{id_mov_auto}",
                            "FECHA": str(fecha_op),
                            "TIPO": "Ingreso (Cobro)",
                            "CONCEPTO / DETALLE": f"Cobro de {id_mov_auto} - {concepto}",
                            "MONTO": valor,
                            "REF_ORIGEN": id_mov_auto
                        }
                        supabase.table("BALANCE").insert(data_balance).execute()
                        
                    st.success("¡Deuda registrada y reflejada en el balance con éxito!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

# ==========================================
# TAB 2: DEUDAS POR PAGAR
# ==========================================
with tab2:
    st.subheader("Listado de Deudas por Pagar")
    df_pagar = fetch_table("DEUDA_X_PAGAR")
    
    if not df_pagar.empty:
        if "ESTATUS" in df_pagar.columns:
            estatus_list_p = ["Todos"] + list(df_pagar["ESTATUS"].dropna().unique())
            filtro_p = st.selectbox("Filtrar por Estatus:", estatus_list_p, key="filtro_pagar")
            if filtro_p != "Todos":
                df_pagar = df_pagar[df_pagar["ESTATUS"] == filtro_p]
                
        st.dataframe(df_pagar, use_container_width=True)
    else:
        st.info("No hay registros en la tabla DEUDA_X_PAGAR.")
        
    with st.expander("➕ Registrar Nueva Deuda por Pagar"):
        id_mov_p_auto = generar_id("CXP")
        
        with st.form("form_nueva_deuda_pagar"):
            st.text_input("ID Movimiento (Generado Automáticamente)", value=id_mov_p_auto, disabled=True)
            
            venta_gasto_p = st.selectbox("Tipo", ["Venta", "Gasto"], key="vg_pagar")
            estatus_p = st.selectbox("Estatus", ["Pendiente", "Pagado", "Parcial"], key="est_pagar")
            valor_p = st.number_input("Valor ($)", min_value=0.0, format="%.2f", key="val_pagar")
            
            df_prov = fetch_table("PROVEEDORES")
            lista_prov = df_prov["ID_PROVEEDOR"].tolist() if not df_prov.empty else []
            proveedor = st.selectbox("Proveedor", lista_prov)
            
            fecha_op_p = st.date_input("Fecha de Operación", key="fec_pagar")
            concepto_p = st.text_area("Concepto / Detalle", key="con_pagar")
            
            submit_pagar = st.form_submit_button("Guardar Deuda por Pagar")
            
            if submit_pagar:
                try:
                    data_pagar = {
                        "ID_MOVIMIENTO": id_mov_p_auto,
                        "VENTA_GASTO": venta_gasto_p,
                        "ESTATUS": estatus_p,
                        "VALOR": valor_p,
                        "PROVEEDOR": proveedor,
                        "FECHA_OPERACION": str(fecha_op_p),
                        "CONCEPTO": concepto_p
                    }
                    supabase.table("DEUDA_X_PAGAR").insert(data_pagar).execute()
                    
                    if estatus_p in ["Pagado", "Parcial"]:
                        data_balance = {
                            "ID_BALANCE": f"BAL-{id_mov_p_auto}",
                            "FECHA": str(fecha_op_p),
                            "TIPO": "Egreso (Pago)",
                            "CONCEPTO / DETALLE": f"Pago de {id_mov_p_auto} - {concepto_p}",
                            "MONTO": valor_p,
                            "REF_ORIGEN": id_mov_p_auto
                        }
                        supabase.table("BALANCE").insert(data_balance).execute()
                        
                    st.success("¡Deuda por pagar registrada y reflejada en el balance!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

# ==========================================
# TAB 3: BALANCE AUTOMÁTICO
# ==========================================
with tab3:
    st.subheader("📈 Balance Financiero Automático")
    df_balance = fetch_table("BALANCE")
    
    if not df_balance.empty:
        ingresos = df_balance[df_balance["TIPO"].str.contains("Ingreso|Cobro", case=False, na=False)]["MONTO"].sum()
        egresos = df_balance[df_balance["TIPO"].str.contains("Egreso|Pago", case=False, na=False)]["MONTO"].sum()
        balance_neto = ingresos - egresos
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Cobrado (Ingresos)", f"${ingresos:,.2f}")
        col2.metric("Total Pagado (Egresos)", f"${egresos:,.2f}")
        col3.metric("Balance Neto", f"${balance_neto:,.2f}", delta=f"${balance_neto:,.2f}")
        st.markdown("---")
        
        st.markdown("### Historial de Movimientos que Afectan el Balance")
        st.dataframe(df_balance, use_container_width=True)
    else:
        st.info("Aún no hay movimientos liquidados (Pagados/Parciales) que alimenten el balance.")

# ==========================================
# TAB 4: CLIENTES Y PROVEEDORES
# ==========================================
with tab4:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Catálogo de Clientes")
        df_cli = fetch_table("CLIENTES")
        st.dataframe(df_cli, use_container_width=True)
        
        with st.expander("➕ Agregar Cliente"):
            id_cli_auto = generar_id("CLI")
            with st.form("form_cliente"):
                st.text_input("ID Cliente (Generado Automáticamente)", value=id_cli_auto, disabled=True)
                nombre_cli = st.text_input("Nombre Comercial")
                rep_cli = st.text_input("Representante Legal")
                rfc_cli = st.text_input("RFC")
                com_cli = st.text_input("Comentarios")
                
                sub_cli = st.form_submit_button("Guardar Cliente")
                if sub_cli:
                    try:
                        supabase.table("CLIENTES").insert({
                            "ID_CLIENTE": id_cli_auto,
                            "NOMBRE_COMERCIAL": nombre_cli,
                            "REP_LEGAL": rep_cli,
                            "RFC": rfc_cli,
                            "COMENTARIOS": com_cli
                        }).execute()
                        st.success("Cliente guardado exitosamente")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                        
    with col2:
        st.subheader("Catálogo de Proveedores")
        df_pro = fetch_table("PROVEEDORES")
        st.dataframe(df_pro, use_container_width=True)
        
        with st.expander("➕ Agregar Proveedor"):
            id_pro_auto = generar_id("PROV")
            with st.form("form_proveedor"):
                st.text_input("ID Proveedor (Generado Automáticamente)", value=id_pro_auto, disabled=True)
                nombre_pro = st.text_input("Nombre Comercial Proveedor")
                rep_pro = st.text_input("Representante Legal")
                rfc_pro = st.text_input("RFC")
                com_pro = st.text_input("Comentarios")
                
                sub_pro = st.form_submit_button("Guardar Proveedor")
                if sub_pro:
                    try:
                        supabase.table("PROVEEDORES").insert({
                            "ID_PROVEEDOR": id_pro_auto,
                            "NOMBRE_COMERCIAL": nombre_pro,
                            "REP_LEGAL": rep_pro,
                            "RFC": rfc_pro,
                            "COMENTARIOS": com_pro
                        }).execute()
                        st.success("Proveedor guardado exitosamente")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

# ==========================================
# TAB 5: PENALIZACIONES
# ==========================================
with tab5:
    st.subheader("Registro de Penalizaciones")
    df_pen = fetch_table("PENALIZACIONES")
    st.dataframe(df_pen, use_container_width=True)
    
    with st.expander("➕ Registrar Penalización"):
        id_pen_auto = generar_id("PEN")
        with st.form("form_penalizacion"):
            st.text_input("ID Penalización (Generado Automáticamente)", value=id_pen_auto, disabled=True)
            tipo_pen = st.text_input("Tipo de Penalización")
            fecha_pen = st.date_input("Fecha")
            motivo_pen = st.text_area("Motivo")
            monto_pen = st.number_input("Monto ($)", min_value=0.0, format="%.2f")
            
            sub_pen = st.form_submit_button("Guardar Penalización")
            if sub_pen:
                try:
                    supabase.table("PENALIZACIONES").insert({
                        "ID_PENALIZACION": id_pen_auto,
                        "TIPO": tipo_pen,
                        "FECHA": str(fecha_pen),
                        "MOTIVO": motivo_pen,
                        "MONTO": monto_pen
                    }).execute()
                    st.success("Penalización registrada con éxito")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
