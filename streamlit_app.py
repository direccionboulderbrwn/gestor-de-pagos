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
    
    if not df_cobrar.empty and "FECHA_OPERACION" in df_cobrar.columns:
        # Extraer años/meses disponibles para el filtro de periodo
        df_cobrar["PERIODO"] = pd.to_datetime(df_cobrar["FECHA_OPERACION"], errors='coerce').dt.strftime('%Y-%m')
        periodos_disponibles = ["Todos"] + sorted(df_cobrar["PERIODO"].dropna().unique().tolist(), reverse=True)
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            periodo_sel = st.selectbox("Seleccionar Periodo (Mes):", periodos_disponibles, key="per_cobrar")
        with col_f2:
            estatus_list = ["Todos"] + list(df_cobrar["ESTATUS"].dropna().unique())
            filtro_est = st.selectbox("Filtrar por Estatus:", estatus_list, key="est_cobrar")
            
        # Aplicar filtros
        df_filtrado = df_cobrar.copy()
        if periodo_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado["PERIODO"] == periodo_sel]
        if filtro_est != "Todos":
            df_filtrado = df_filtrado[df_filtrado["ESTATUS"] == filtro_est]
            
        # Mostrar tabla sin la columna auxiliar de periodo
        st.dataframe(df_filtrado.drop(columns=["PERIODO"], errors="ignore"), use_container_width=True)
        
        # --- MÓDULO DE ELIMINACIÓN ---
        with st.expander("🗑️ Eliminar Registro de Deuda por Cobrar"):
            ids_disponibles = df_filtrado["ID_MOVIMIENTO"].tolist() if not df_filtrado.empty else []
            if ids_disponibles:
                id_a_borrar = st.selectbox("Selecciona el ID de Movimiento a eliminar:", ids_disponibles, key="del_cobrar")
                if st.button("Eliminar Registro Seleccionado", key="btn_del_cobrar"):
                    try:
                        supabase.table("DEUDAS_X_COBRAR").delete().eq("ID_MOVIMIENTO", id_a_borrar).execute()
                        st.success(f"Registro {id_a_borrar} eliminado correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")
            else:
                st.info("No hay registros en este periodo para eliminar.")
    else:
        st.info("No hay registros suficientes o falta la fecha de operación en DEUDAS_X_COBRAR.")
        
    with st.expander("➕ Registrar Nueva Deuda por Cobrar"):
        id_mov_auto = generar_id("CXC")
        with st.form("form_nueva_deuda_cobrar"):
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
    
    if not df_pagar.empty and "FECHA_OPERACION" in df_pagar.columns:
        df_pagar["PERIODO"] = pd.to_datetime(df_pagar["FECHA_OPERACION"], errors='coerce').dt.strftime('%Y-%m')
        periodos_p_disp = ["Todos"] + sorted(df_pagar["PERIODO"].dropna().unique().tolist(), reverse=True)
        
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            periodo_sel_p = st.selectbox("Seleccionar Periodo (Mes):", periodos_p_disp, key="per_pagar")
        with col_p2:
            estatus_list_p = ["Todos"] + list(df_pagar["ESTATUS"].dropna().unique())
            filtro_est_p = st.selectbox("Filtrar por Estatus:", estatus_list_p, key="est_pagar")
            
        df_filtrado_p = df_pagar.copy()
        if periodo_sel_p != "Todos":
            df_filtrado_p = df_filtrado_p[df_filtrado_p["PERIODO"] == periodo_sel_p]
        if filtro_est_p != "Todos":
            df_filtrado_p = df_filtrado_p[df_filtrado_p["ESTATUS"] == filtro_est_p]
            
        st.dataframe(df_filtrado_p.drop(columns=["PERIODO"], errors="ignore"), use_container_width=True)
        
        # --- MÓDULO DE ELIMINACIÓN ---
        with st.expander("🗑️ Eliminar Registro de Deuda por Pagar"):
            ids_p_disp = df_filtrado_p["ID_MOVIMIENTO"].tolist() if not df_filtrado_p.empty else []
            if ids_p_disp:
                id_p_a_borrar = st.selectbox("Selecciona el ID de Movimiento a eliminar:", ids_p_disp, key="del_pagar")
                if st.button("Eliminar Registro Seleccionado", key="btn_del_pagar"):
                    try:
                        supabase.table("DEUDA_X_PAGAR").delete().eq("ID_MOVIMIENTO", id_p_a_borrar).execute()
                        st.success(f"Registro {id_p_a_borrar} eliminado correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")
            else:
                st.info("No hay registros en este periodo para eliminar.")
    else:
        st.info("No hay registros suficientes o falta la fecha de operación en DEUDA_X_PAGAR.")
        
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
# TAB 3: BALANCE AUTOMÁTICO (CON FILTRO DE PERIODO)
# ==========================================
with tab3:
    st.subheader("📈 Balance Financiero Automático")
    df_balance = fetch_table("BALANCE")
    
    if not df_balance.empty and "FECHA" in df_balance.columns:
        df_balance["PERIODO"] = pd.to_datetime(df_balance["FECHA"], errors='coerce').dt.strftime('%Y-%m')
        periodos_bal = ["Todos"] + sorted(df_balance["PERIODO"].dropna().unique().tolist(), reverse=True)
        
        periodo_sel_bal = st.selectbox("Filtrar Balance por Periodo (Mes):", periodos_bal, key="per_balance")
        
        df_bal_filtrado = df_balance.copy()
        if periodo_sel_bal != "Todos":
            df_bal_filtrado = df_bal_filtrado[df_bal_filtrado["PERIODO"] == periodo_sel_bal]
            
        # Calcular métricas basadas en el periodo filtrado
        ingresos = df_bal_filtrado[df_bal_filtrado["TIPO"].str.contains("Ingreso|Cobro", case=False, na=False)]["MONTO"].sum()
        egresos = df_bal_filtrado[df_bal_filtrado["TIPO"].str.contains("Egreso|Pago", case=False, na=False)]["MONTO"].sum()
        balance_neto = ingresos - egresos
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Cobrado (Ingresos)", f"${ingresos:,.2f}")
        col2.metric("Total Pagado (Egresos)", f"${egresos:,.2f}")
        col3.metric("Balance Neto", f"${balance_neto:,.2f}", delta=f"${balance_neto:,.2f}")
        st.markdown("---")
        
        st.markdown(f"### Historial de Movimientos ({periodo_sel_bal})")
        st.dataframe(df_bal_filtrado.drop(columns=["PERIODO"], errors="ignore"), use_container_width=True)
    else:
        st.info("Aún no hay movimientos liquidados que alimenten el balance.")

# ==========================================
# TAB 4: CLIENTES Y PROVEEDORES
# ==========================================
# ==========================================
# TAB 4: CLIENTES Y PROVEEDORES
# ==========================================
with tab4:
    # Inicializar contadores de sesión para forzar la limpieza de formularios al guardar
    if "form_cli_key" not in st.session_state:
        st.session_state["form_cli_key"] = 0
    if "form_pro_key" not in st.session_state:
        st.session_state["form_pro_key"] = 0

    col1, col2 = st.columns(2)
    
    # --- CLIENTES ---
    with col1:
        st.subheader("Catálogo de Clientes")
        df_cli = fetch_table("CLIENTES")
        st.dataframe(df_cli, use_container_width=True)
        
        # Eliminar Cliente
        with st.expander("🗑️ Eliminar Cliente"):
            ids_cli = df_cli["ID_CLIENTE"].tolist() if not df_cli.empty else []
            if ids_cli:
                cli_del = st.selectbox("Selecciona ID de Cliente:", ids_cli, key="del_cli")
                if st.button("Eliminar Cliente", key="btn_del_cli"):
                    try:
                        supabase.table("CLIENTES").delete().eq("ID_CLIENTE", cli_del).execute()
                        st.success("Cliente eliminado con éxito.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar (asegúrate de que no tenga deudas activas asociadas): {e}")
            else:
                st.info("No hay clientes registrados para eliminar.")
                        
        with st.expander("➕ Agregar Cliente"):
            # Generar ID dinámico basado en el estado de sesión para que cambie al guardarse
            id_cli_auto = generar_id("CLI")
            
            # Usamos la llave dinámica (form_cli_key) para reiniciar el formulario por completo
            with st.form(f"form_cliente_{st.session_state['form_cli_key']}"):
                st.text_input("ID Cliente (Generado Automáticamente)", value=id_cli_auto, disabled=True)
                nombre_cli = st.text_input("Nombre Comercial", key=f"nom_cli_{st.session_state['form_cli_key']}")
                rep_cli = st.text_input("Representante Legal", key=f"rep_cli_{st.session_state['form_cli_key']}")
                rfc_cli = st.text_input("RFC", key=f"rfc_cli_{st.session_state['form_cli_key']}")
                fecha_alta_cli = st.date_input("Fecha de Alta", key=f"fec_cli_{st.session_state['form_cli_key']}")
                com_cli = st.text_input("Comentarios", key=f"com_cli_{st.session_state['form_cli_key']}")
                
                sub_cli = st.form_submit_button("Guardar Cliente")
                if sub_cli:
                    try:
                        supabase.table("CLIENTES").insert({
                            "ID_CLIENTE": id_cli_auto,
                            "NOMBRE_COMERCIAL": nombre_cli,
                            "REP_LEGAL": rep_cli,
                            "RFC": rfc_cli,
                            "FECHA_INGRESO": str(fecha_alta_cli),
                            "COMENTARIOS": com_cli
                        }).execute()
                        
                        # Incrementamos la llave para forzar que el formulario se limpie y cree un nuevo ID
                        st.session_state["form_cli_key"] += 1
                        st.success("¡Cliente guardado exitosamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")
                        
    # --- PROVEEDORES ---
    with col2:
        st.subheader("Catálogo de Proveedores")
        df_pro = fetch_table("PROVEEDORES")
        st.dataframe(df_pro, use_container_width=True)
        
        # Eliminar Proveedor
        with st.expander("🗑️ Eliminar Proveedor"):
            ids_pro = df_pro["ID_PROVEEDOR"].tolist() if not df_pro.empty else []
            if ids_pro:
                pro_del = st.selectbox("Selecciona ID de Proveedor:", ids_pro, key="del_pro")
                if st.button("Eliminar Proveedor", key="btn_del_pro"):
                    try:
                        supabase.table("PROVEEDORES").delete().eq("ID_PROVEEDOR", pro_del).execute()
                        st.success("Proveedor eliminado con éxito.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")
            else:
                st.info("No hay proveedores registrados para eliminar.")
                        
        with st.expander("➕ Agregar Proveedor"):
            id_pro_auto = generar_id("PROV")
            
            with st.form(f"form_proveedor_{st.session_state['form_pro_key']}"):
                st.text_input("ID Proveedor (Generado Automáticamente)", value=id_pro_auto, disabled=True)
                nombre_pro = st.text_input("Nombre Comercial Proveedor", key=f"nom_pro_{st.session_state['form_pro_key']}")
                rep_pro = st.text_input("Representante Legal", key=f"rep_pro_{st.session_state['form_pro_key']}")
                rfc_pro = st.text_input("RFC", key=f"rfc_pro_{st.session_state['form_pro_key']}")
                fecha_alta_pro = st.date_input("Fecha de Alta", key=f"fec_pro_{st.session_state['form_pro_key']}")
                com_pro = st.text_input("Comentarios", key=f"com_pro_{st.session_state['form_pro_key']}")
                
                sub_pro = st.form_submit_button("Guardar Proveedor")
                if sub_pro:
                    try:
                        supabase.table("PROVEEDORES").insert({
                            "ID_PROVEEDOR": id_pro_auto,
                            "NOMBRE_COMERCIAL": nombre_pro,
                            "REP_LEGAL": rep_pro,
                            "RFC": rfc_pro,
                            "FECHA_INGRESO": str(fecha_alta_pro),
                            "COMENTARIOS": com_pro
                        }).execute()
                        
                        # Incrementamos la llave para reiniciar el formulario de proveedores
                        st.session_state["form_pro_key"] += 1
                        st.success("¡Proveedor guardado exitosamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")
# ==========================================
# TAB 5: PENALIZACIONES
# ==========================================
with tab5:
    st.subheader("Registro de Penalizaciones")
    df_pen = fetch_table("PENALIZACIONES")
    
    if not df_pen.empty and "FECHA" in df_pen.columns:
        df_pen["PERIODO"] = pd.to_datetime(df_pen["FECHA"], errors='coerce').dt.strftime('%Y-%m')
        periodos_pen = ["Todos"] + sorted(df_pen["PERIODO"].dropna().unique().tolist(), reverse=True)
        
        periodo_sel_pen = st.selectbox("Filtrar Penalizaciones por Periodo (Mes):", periodos_pen, key="per_pen")
        
        df_pen_filtrado = df_pen.copy()
        if periodo_sel_pen != "Todos":
            df_pen_filtrado = df_pen_filtrado[df_pen_filtrado["PERIODO"] == periodo_sel_pen]
            
        st.dataframe(df_pen_filtrado.drop(columns=["PERIODO"], errors="ignore"), use_container_width=True)
        
        # --- MÓDULO DE ELIMINACIÓN ---
        with st.expander("🗑️ Eliminar Penalización"):
            ids_pen = df_pen_filtrado["ID_PENALIZACION"].tolist() if not df_pen_filtrado.empty else []
            if ids_pen:
                pen_del = st.selectbox("Selecciona ID de Penalización:", ids_pen, key="del_pen")
                if st.button("Eliminar Penalización", key="btn_del_pen"):
                    try:
                        supabase.table("PENALIZACIONES").delete().eq("ID_PENALIZACION", pen_del).execute()
                        st.success("Penalización eliminada con éxito.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")
            else:
                st.info("No hay penalizaciones en este periodo para eliminar.")
    else:
        st.info("No hay registros en la tabla PENALIZACIONES.")
        
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
