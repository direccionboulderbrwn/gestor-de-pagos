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
    st.subheader("💰 Listado de Deudas por Cobrar a Clientes")
    df_cobrar = fetch_table("DEUDAS_X_COBRAR")
    df_cli_tabla = fetch_table("CLIENTES")
    
    if not df_cobrar.empty and not df_cli_tabla.empty:
        if "CLIENTE" in df_cobrar.columns and "ID_CLIENTE" in df_cli_tabla.columns:
            df_cobrar = df_cobrar.merge(
                df_cli_tabla[["ID_CLIENTE", "NOMBRE_COMERCIAL"]],
                left_on="CLIENTE",
                right_on="ID_CLIENTE",
                how="left"
            )
            df_cobrar = df_cobrar.rename(columns={"NOMBRE_COMERCIAL": "NOMBRE_CLIENTE"})
            cols = [c for c in df_cobrar.columns if c not in ["CLIENTE", "ID_CLIENTE", "NOMBRE_CLIENTE"]]
            if "ESTATUS" in cols:
                idx = cols.index("ESTATUS")
                cols.insert(idx, "NOMBRE_CLIENTE")
            else:
                cols.append("NOMBRE_CLIENTE")
            df_cobrar = df_cobrar[cols]
            if "CLIENTE" in df_cobrar.columns:
                df_cobrar = df_cobrar.drop(columns=["CLIENTE"])

    if not df_cobrar.empty and "FECHA_OPERACION" in df_cobrar.columns:
        df_cobrar["PERIODO"] = pd.to_datetime(df_cobrar["FECHA_OPERACION"], errors='coerce').dt.strftime('%Y-%m')
        periodos_disponibles = ["Todos"] + sorted(df_cobrar["PERIODO"].dropna().unique().tolist(), reverse=True)
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            periodo_sel = st.selectbox("Seleccionar Periodo (Mes):", periodos_disponibles, key="per_cobrar_filtro")
        with col_f2:
            estatus_list = ["Todos", "Pendiente", "Parcial", "Pagado"]
            filtro_est = st.selectbox("Filtrar por Estatus:", estatus_list, key="est_cobrar_filtro", index=1)
            
        df_filtrado = df_cobrar.copy()
        if periodo_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado["PERIODO"] == periodo_sel]
        if filtro_est != "Todos":
            df_filtrado = df_filtrado[df_filtrado["ESTATUS"] == filtro_est]
            
        st.dataframe(df_filtrado.drop(columns=["PERIODO"], errors="ignore"), use_container_width=True)
        
        with st.expander("💵 Realizar Abono / Cobrar Deuda (Liquidar)"):
            df_pendientes_cobrar = df_cobrar[df_cobrar["ESTATUS"].isin(["Pendiente", "Parcial"])]
            ids_pendientes_cobrar = df_pendientes_cobrar["ID_MOVIMIENTO"].tolist() if not df_pendientes_cobrar.empty else []
            
            if ids_pendientes_cobrar:
                id_deuda_cobrar = st.selectbox("Selecciona ID de Deuda a Cobrar/Abonar:", ids_pendientes_cobrar, key="sel_deuda_abonar_cobrar")
                
                fila_deuda_c = df_pendientes_cobrar[df_pendientes_cobrar["ID_MOVIMIENTO"] == id_deuda_cobrar].iloc[0]
                val_original_c = float(fila_deuda_c["VALOR"])
                cli_afectado = fila_deuda_c.get("NOMBRE_CLIENTE", "Cliente")
                concepto_actual_c = fila_deuda_c.get("CONCEPTO", "")
                
                st.info(f"Monto Total de la Factura: **${val_original_c:,.2f}** | Cliente: **{cli_afectado}**")
                
                monto_abono_c = st.number_input("Monto del Abono / Cobro ($)", min_value=0.01, max_value=float(val_original_c), value=float(val_original_c), format="%.2f", key="input_monto_abono_cobrar")
                fecha_abono_c = st.date_input("Fecha del Cobro", key="fec_abono_cobrar")
                nuevo_estatus_c = st.selectbox("Estatus resultante tras el abono", ["Pagado", "Parcial"], key="nuevo_estatus_abono_cobrar")
                
                if st.button("Confirmar Cobro / Abono", key="btn_confirmar_abono_cobrar"):
                    try:
                        supabase.table("DEUDAS_X_COBRAR").update({"ESTATUS": nuevo_estatus_c}).eq("ID_MOVIMIENTO", id_deuda_cobrar).execute()
                        
                        id_bal_auto_c = generar_id("BAL-COBRO")
                        data_balance_cobro = {
                            "ID_BALANCE": id_bal_auto_c,
                            "FECHA": str(fecha_abono_c),
                            "TIPO": f"Ingreso (Cobro {nuevo_estatus_c})",
                            "CONCEPTO / DETALLE": f"Cobro a {cli_afectado} ({id_deuda_cobrar}) - {concepto_actual_c}",
                            "MONTO": monto_abono_c,
                            "REF_ORIGEN": id_deuda_cobrar
                        }
                        supabase.table("BALANCE").insert(data_balance_cobro).execute()
                        
                        st.success(f"¡Cobro de ${monto_abono_c:,.2f} registrado y enviado al Balance como Ingreso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al procesar el cobro: {e}")
            else:
                st.info("No hay deudas por cobrar pendientes o parciales en este filtro.")

        with st.expander("🗑️ Eliminar Registro de Deuda por Cobrar"):
            ids_disponibles = df_filtrado["ID_MOVIMIENTO"].tolist() if not df_filtrado.empty else []
            if ids_disponibles:
                id_a_borrar = st.selectbox("Selecciona el ID de Movimiento a eliminar:", ids_disponibles, key="del_cobrar_sel")
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
        st.info("No hay registros suficientes en DEUDAS_X_COBRAR.")
        
    with st.expander("➕ Registrar Nueva Deuda por Cobrar (Con Penalización, IVA y RESICO)"):
        id_mov_auto = generar_id("CXC")
        with st.form("form_nueva_deuda_cobrar"):
            st.text_input("ID Movimiento (Generado Automáticamente)", value=id_mov_auto, disabled=True, key="txt_id_cxc")
            venta_gasto = st.selectbox("Tipo", ["Venta", "Gasto"], key="vg_cxc_form")
            estatus = st.selectbox("Estatus", ["Pendiente", "Pagado", "Parcial"], key="est_cxc_form")
            
            df_clientes = fetch_table("CLIENTES")
            if not df_clientes.empty:
                mapa_clis = dict(zip(df_clientes["NOMBRE_COMERCIAL"], df_clientes["ID_CLIENTE"]))
                lista_nombres_cli = list(mapa_clis.keys())
            else:
                mapa_clis = {}
                lista_nombres_cli = []
                
            cliente_nombre_sel = st.selectbox("Cliente", lista_nombres_cli, key="cli_cxc_form")
            fecha_op = st.date_input("Fecha de Operación", key="fec_cxc_form")
            
            st.markdown("---")
            st.markdown("##### 🧮 Cálculo de Importes, Penalización y Tasas Fiscales")
            monto_base = st.number_input("Monto Base / Subtotal Factura ($)", min_value=0.0, format="%.2f", key="val_base_cxc")
            
            aplica_pen_cli = st.checkbox("¿El cliente aplicó penalización a este monto?", key="chk_pen_cli")
            monto_penalizacion = st.number_input("Monto de la Penalización ($)", min_value=0.0, format="%.2f", key="val_pen_cli")
            motivo_penalizacion = st.text_input("Motivo o detalle de la Penalización", key="mot_pen_cli")
            
            col_imp1, col_imp2 = st.columns(2)
            with col_imp1:
                aplicar_iva = st.checkbox("Agregar IVA (16%)", value=True, key="chk_iva_cxc")
            with col_imp2:
                aplicar_resico = st.checkbox("Régimen RESICO Persona Física (Retención ISR 1.25% y Retención IVA 10.66%)", value=False, key="chk_resico_cxc")
                
            concepto = st.text_area("Concepto / Detalle general", key="con_cxc_form")
            
            # --- CÁLCULO FINANCIERO Y FISCAL ---
            penalizacion_real = monto_penalizacion if aplica_pen_cli else 0.0
            
            subtotal_neto = max(0.0, monto_base - penalizacion_real)
            iva_monto = subtotal_neto * 0.16 if aplicar_iva else 0.0
            ret_isr = subtotal_neto * 0.0125 if aplicar_resico else 0.0
            ret_iva = subtotal_neto * (2/3 * 0.16) if aplicar_resico else 0.0
            monto_final_neto = subtotal_neto + iva_monto - ret_isr - ret_iva
            
            st.info(f"💡 Subtotal Neto: ${subtotal_neto:,.2f} | IVA: ${iva_monto:,.2f} | Retenciones: -${(ret_isr + ret_iva):,.2f} | Monto Final: ${monto_final_neto:,.2f}")
            
            if st.form_submit_button("Guardar Deuda con Desglose Fiscal"):
                if not lista_nombres_cli:
                    st.error("Primero debes registrar clientes en el Catálogo.")
                else:
                    id_cli_real = mapa_clis.get(cliente_nombre_sel)
                    try:
                        detalle_completo = f"{concepto} | Subtotal: ${monto_base:,.2f}"
                        if aplica_pen_cli and penalizacion_real > 0:
                            detalle_completo += f" | Menos Penalización (${penalizacion_real:,.2f}): {motivo_penalizacion}"
                        if aplicar_resico:
                            detalle_completo += f" | Retenciones RESICO aplicadas"

                        data_cobrar = {
                            "ID_MOVIMIENTO": id_mov_auto,
                            "VENTA_GASTO": venta_gasto,
                            "ESTATUS": estatus,
                            "VALOR": monto_final_neto,
                            "CLIENTE": id_cli_real,
                            "FECHA_OPERACION": str(fecha_op),
                            "CONCEPTO": detalle_completo
                        }
                        supabase.table("DEUDAS_X_COBRAR").insert(data_cobrar).execute()
                        
                        if estatus in ["Pagado", "Parcial"]:
                            data_balance = {
                                "ID_BALANCE": f"BAL-{id_mov_auto}",
                                "FECHA": str(fecha_op),
                                "TIPO": f"Ingreso (Cobro {estatus})",
                                "CONCEPTO / DETALLE": f"Cobro neto a {cliente_nombre_sel} - {concepto}",
                                "MONTO": monto_final_neto,
                                "REF_ORIGEN": id_mov_auto
                            }
                            supabase.table("BALANCE").insert(data_balance).execute()
                            
                        st.success("¡Deuda registrada con cálculo fiscal y reflejada correctamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")
# ==========================================
# TAB 2: DEUDAS POR PAGAR Y ABONOS/LIQUIDACIÓN
# ==========================================
with tab2:
    if "form_pago_cond_key" not in st.session_state:
        st.session_state["form_pago_cond_key"] = 0

    st.subheader("📉 Listado de Deudas por Pagar a Proveedores")
    df_pagar = fetch_table("DEUDA_X_PAGAR")
    df_prov_tabla = fetch_table("PROVEEDORES")
    
    if not df_pagar.empty and not df_prov_tabla.empty:
        if "PROVEEDOR" in df_pagar.columns and "ID_PROVEEDOR" in df_prov_tabla.columns:
            df_pagar = df_pagar.merge(
                df_prov_tabla[["ID_PROVEEDOR", "NOMBRE_COMERCIAL"]],
                left_on="PROVEEDOR",
                right_on="ID_PROVEEDOR",
                how="left"
            )
            df_pagar = df_pagar.rename(columns={"NOMBRE_COMERCIAL": "NOMBRE_PROVEEDOR"})
            cols = [c for c in df_pagar.columns if c not in ["PROVEEDOR", "ID_PROVEEDOR", "NOMBRE_PROVEEDOR"]]
            if "ESTATUS" in cols:
                idx = cols.index("ESTATUS")
                cols.insert(idx, "NOMBRE_PROVEEDOR")
            else:
                cols.append("NOMBRE_PROVEEDOR")
            df_pagar = df_pagar[cols]
            if "PROVEEDOR" in df_pagar.columns:
                df_pagar = df_pagar.drop(columns=["PROVEEDOR"])

    if not df_pagar.empty and "FECHA_OPERACION" in df_pagar.columns:
        df_pagar["PERIODO"] = pd.to_datetime(df_pagar["FECHA_OPERACION"], errors='coerce').dt.strftime('%Y-%m')
        periodos_p_disp = ["Todos"] + sorted(df_pagar["PERIODO"].dropna().unique().tolist(), reverse=True)
        
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            periodo_sel_p = st.selectbox("Seleccionar Periodo (Mes):", periodos_p_disp, key="per_pagar_filtro_tab2")
        with col_p2:
            estatus_list_p = ["Todos", "Pendiente", "Parcial", "Pagado"]
            filtro_est_p = st.selectbox("Filtrar por Estatus:", estatus_list_p, key="est_pagar_filtro_tab2", index=1)
            
        df_filtrado_p = df_pagar.copy()
        if periodo_sel_p != "Todos":
            df_filtrado_p = df_filtrado_p[df_filtrado_p["PERIODO"] == periodo_sel_p]
        if filtro_est_p != "Todos":
            df_filtrado_p = df_filtrado_p[df_filtrado_p["ESTATUS"] == filtro_est_p]
            
        st.dataframe(df_filtrado_p.drop(columns=["PERIODO"], errors="ignore"), use_container_width=True)
        
        with st.expander("💸 Realizar Abono / Pagar Deuda (Liquidar)"):
            df_pendientes = df_pagar[df_pagar["ESTATUS"].isin(["Pendiente", "Parcial"])]
            ids_pendientes = df_pendientes["ID_MOVIMIENTO"].tolist() if not df_pendientes.empty else []
            
            if ids_pendientes:
                id_deuda_pagar = st.selectbox("Selecciona ID de Deuda a Pagar/Abonar:", ids_pendientes, key="sel_deuda_abonar")
                
                fila_deuda = df_pendientes[df_pendientes["ID_MOVIMIENTO"] == id_deuda_pagar].iloc[0]
                val_original = float(fila_deuda["VALOR"])
                prov_afectado = fila_deuda.get("NOMBRE_PROVEEDOR", "Proveedor")
                conCEP_actual = fila_deuda.get("CONCEPTO", "")
                
                st.info(f"Monto Total de la Cuenta por Pagar: **${val_original:,.2f}** | Proveedor: **{prov_afectado}**")
                
                monto_abono = st.number_input("Monto del Abono / Pago ($)", min_value=0.01, max_value=float(val_original), value=float(val_original), format="%.2f", key="input_monto_abono")
                fecha_abono = st.date_input("Fecha del Abono", key="fec_abono_pago")
                nuevo_estatus = st.selectbox("Estatus resultante tras el abono", ["Pagado", "Parcial"], key="nuevo_estatus_abono")
                
                if st.button("Confirmar Pago / Abono", key="btn_confirmar_abono"):
                    try:
                        supabase.table("DEUDA_X_PAGAR").update({"ESTATUS": nuevo_estatus}).eq("ID_MOVIMIENTO", id_deuda_pagar).execute()
                        
                        id_bal_auto = generar_id("BAL-PAGO")
                        data_balance_pago = {
                            "ID_BALANCE": id_bal_auto,
                            "FECHA": str(fecha_abono),
                            "TIPO": f"Egreso (Pago {nuevo_estatus})",
                            "CONCEPTO / DETALLE": f"Pago a {prov_afectado} ({id_deuda_pagar}) - {conCEP_actual}",
                            "MONTO": monto_abono,
                            "REF_ORIGEN": id_deuda_pagar
                        }
                        supabase.table("BALANCE").insert(data_balance_pago).execute()
                        
                        st.success(f"¡Pago de ${monto_abono:,.2f} registrado y enviado al Balance como Egreso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al procesar el abono: {e}")
            else:
                st.info("No hay deudas pendientes o parciales en este filtro para abonar.")

        with st.expander("🗑️ Eliminar Registro de Deuda por Pagar"):
            ids_p_disp = df_filtrado_p["ID_MOVIMIENTO"].tolist() if not df_filtrado_p.empty else []
            if ids_p_disp:
                id_p_a_borrar = st.selectbox("Selecciona el ID de Movimiento a eliminar:", ids_p_disp, key="del_pagar_sel_tab2")
                if st.button("Eliminar Registro Seleccionado", key="btn_del_pagar_tab2"):
                    try:
                        supabase.table("DEUDA_X_PAGAR").delete().eq("ID_MOVIMIENTO", id_p_a_borrar).execute()
                        st.success(f"Registro {id_p_a_borrar} eliminado correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")
            else:
                st.info("No hay registros en este periodo para eliminar.")
    else:
        st.info("No hay registros de deudas por pagar.")
        
    with st.expander("➕ Registrar Nueva Deuda por Pagar a Proveedor (Con Penalización e IVA)"):
        id_mov_p_auto = generar_id("CXP")
        with st.form("form_nueva_deuda_pagar"):
            st.text_input("ID Movimiento (Generado Automáticamente)", value=id_mov_p_auto, disabled=True, key="txt_id_cxp_form")
            venta_gasto_p = st.selectbox("Tipo", ["Venta", "Gasto"], key="vg_cxp_form")
            estatus_p = st.selectbox("Estatus", ["Pendiente", "Pagado", "Parcial"], key="est_cxp_form")
            
            df_prov = fetch_table("PROVEEDORES")
            if not df_prov.empty:
                mapa_provs = dict(zip(df_prov["NOMBRE_COMERCIAL"], df_prov["ID_PROVEEDOR"]))
                lista_nombres_p = list(mapa_provs.keys())
            else:
                mapa_provs = {}
                lista_nombres_p = []
                
            proveedor_nombre_sel = st.selectbox("Proveedor", lista_nombres_p, key="prov_cxp_form")
            fecha_op_p = st.date_input("Fecha de Operación", key="fec_cxp_form")
            
            st.markdown("---")
            st.markdown("##### 🧮 Cálculo de Importes, Descuentos/Penalizaciones al Proveedor e IVA")
            monto_base_p = st.number_input("Monto Base / Subtotal Factura Proveedor ($)", min_value=0.0, format="%.2f", key="val_base_cxp")
            
            col_ppen1, col_ppen2 = st.columns(2)
            with col_ppen1:
                aplica_pen_prov = st.checkbox("¿Le apliqué penalización o descuento a este proveedor?", key="chk_pen_prov")
            with col_ppen2:
                monto_penalizacion_p = st.number_input("Monto de Descuento/Penalización ($)", min_value=0.0, format="%.2f", key="val_pen_prov") if aplica_pen_prov else 0.0
                
            motivo_penalizacion_p = st.text_input("Motivo de la penalización al proveedor", key="mot_pen_prov") if aplica_pen_prov else ""
            
            aplicar_iva_p = st.checkbox("Agregar IVA (16%)", value=True, key="chk_iva_cxp")
            concepto_p = st.text_area("Concepto / Detalle general", key="con_cxp_form")
            
            # --- CÁLCULO FINANCIERO ---
            subtotal_neto_p = max(0.0, monto_base_p - monto_penalizacion_p)
            iva_monto_p = subtotal_neto_p * 0.16 if aplicar_iva_p else 0.0
            monto_final_neto_p = subtotal_neto_p + iva_monto_p
            
            st.info(f"💡 **Resumen Calculado:** Subtotal Neto a Pagar: **${subtotal_neto_p:,.2f}** | IVA: **${iva_monto_p:,.2f}** | **Total Final Neto: ${monto_final_neto_p:,.2f}**")
            
            if st.form_submit_button("Guardar Deuda por Pagar"):
                if not lista_nombres_p:
                    st.error("Primero debes registrar proveedores en el Catálogo.")
                else:
                    id_prov_real = mapa_provs.get(proveedor_nombre_sel)
                    try:
                        detalle_completo_p = f"{concepto_p} | Subtotal: ${monto_base_p:,.2f}"
                        if aplica_penalizacion_p:
                            detalle_completo_p += f" | Menos Penalización al proveedor (${monto_penalizacion_p:,.2f}): {motivo_penalizacion_p}"

                        data_pagar = {
                            "ID_MOVIMIENTO": id_mov_p_auto,
                            "VENTA_GASTO": venta_gasto_p,
                            "ESTATUS": estatus_p,
                            "VALOR": monto_final_neto_p,
                            "PROVEEDOR": id_prov_real,
                            "FECHA_OPERACION": str(fecha_op_p),
                            "CONCEPTO": detalle_completo_p
                        }
                        supabase.table("DEUDA_X_PAGAR").insert(data_pagar).execute()
                        
                        if estatus_p in ["Pagado", "Parcial"]:
                            data_balance = {
                                "ID_BALANCE": f"BAL-{id_mov_p_auto}",
                                "FECHA": str(fecha_op_p),
                                "TIPO": f"Egreso (Pago {estatus_p})",
                                "CONCEPTO / DETALLE": f"Pago neto a {proveedor_nombre_sel} - {concepto_p}",
                                "MONTO": monto_final_neto_p,
                                "REF_ORIGEN": id_mov_p_auto
                            }
                            supabase.table("BALANCE").insert(data_balance).execute()
                            
                        st.success("¡Deuda por pagar registrada con éxito!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

    st.markdown("---")
    st.subheader("🚚 Control de Pagos y Abonos a Conductores (Modelo Mixto)")
    
    df_conds = fetch_table("CONDUCTORES")
    if not df_conds.empty and not df_prov_tabla.empty:
        df_conds = df_conds.merge(
            df_prov_tabla[["ID_PROVEEDOR", "NOMBRE_COMERCIAL"]],
            on="ID_PROVEEDOR",
            how="left"
        ).rename(columns={"NOMBRE_COMERCIAL": "PROVEEDOR_ASOCIADO"})
        st.dataframe(df_conds.drop(columns=["ID_PROVEEDOR"], errors="ignore"), use_container_width=True)
    else:
        st.info("No hay conductores registrados en el sistema.")

    with st.expander("➕ Registrar Pago o Abono a Conductor"):
        id_pago_cond_auto = generar_id("PAG-COND")
        with st.form(f"form_pago_conductor_{st.session_state['form_pago_cond_key']}"):
            st.text_input("ID Transacción (Automático)", value=id_pago_cond_auto, disabled=True, key=f"txt_id_pago_cond_{st.session_state['form_pago_cond_key']}")
            
            if not df_conds.empty:
                mapa_conds = dict(zip(df_conds["NOMBRE_CONDUCTOR"], df_conds["ID_CONDUCTOR"]))
                lista_nombres_c = list(mapa_conds.keys())
            else:
                mapa_conds = {}
                lista_nombres_c = []
                
            conductor_sel = st.selectbox("Seleccionar Conductor", lista_nombres_c, key=f"sel_cond_pago_form_{st.session_state['form_pago_cond_key']}")
            monto_cond = st.number_input("Monto del Pago / Abono ($)", min_value=0.0, format="%.2f", key=f"val_pago_cond_form_{st.session_state['form_pago_cond_key']}")
            fecha_pago_cond = st.date_input("Fecha de Pago", key=f"fec_pago_cond_form_{st.session_state['form_pago_cond_key']}")
            concepto_pago_cond = st.text_area("Concepto (ej. Nómina quincenal, Viáticos, Anticipo)", key=f"con_pago_cond_form_{st.session_state['form_pago_cond_key']}")
            
            if st.form_submit_button("Registrar Pago a Conductor"):
                if not lista_nombres_c:
                    st.error("No hay conductores disponibles para realizar pagos.")
                else:
                    id_cond_real = mapa_conds.get(conductor_sel)
                    try:
                        data_balance_cond = {
                            "ID_BALANCE": id_pago_cond_auto,
                            "FECHA": str(fecha_pago_cond),
                            "TIPO": "Egreso (Pago Conductor)",
                            "CONCEPTO / DETALLE": f"Pago a Conductor: {conductor_sel} - {concepto_pago_cond}",
                            "MONTO": monto_cond,
                            "REF_ORIGEN": id_cond_real
                        }
                        supabase.table("BALANCE").insert(data_balance_cond).execute()
                        st.session_state["form_pago_cond_key"] += 1
                        st.success(f"¡Pago de ${monto_cond:,.2f} a {conductor_sel} registrado y descontado del balance correctamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al registrar el pago: {e}")
# ==========================================
# TAB 3: BALANCE AUTOMÁTICO (Ajustado a la lógica correcta)
# ==========================================
with tab3:
    st.subheader("📈 Balance Financiero Automático")
    df_balance = fetch_table("BALANCE")
    
    if not df_balance.empty and "FECHA" in df_balance.columns:
        df_balance["PERIODO"] = pd.to_datetime(df_balance["FECHA"], errors='coerce').dt.strftime('%Y-%m')
        periodos_bal = ["Todos"] + sorted(df_balance["PERIODO"].dropna().unique().tolist(), reverse=True)
        
        periodo_sel_bal = st.selectbox("Filtrar Balance por Periodo (Mes):", periodos_bal, key="per_balance_tab3")
        
        df_bal_filtrado = df_balance.copy()
        if periodo_sel_bal != "Todos":
            df_bal_filtrado = df_bal_filtrado[df_bal_filtrado["PERIODO"] == periodo_sel_bal]
            
        # Ingresos: Cobros normales + Penalizaciones aplicadas a proveedores (descuentos a nuestro favor)
        ingresos = df_bal_filtrado[
            df_bal_filtrado["TIPO"].str.contains("Ingreso|Cobro|Penalización Proveedor", case=False, na=False)
        ]["MONTO"].sum()
        
        # Egresos: Pagos normales + Pagos a conductores + Penalizaciones aplicadas por clientes (descuentos que nos hacen)
        egresos = df_bal_filtrado[
            df_bal_filtrado["TIPO"].str.contains("Egreso|Pago|Penalización Cliente", case=False, na=False)
        ]["MONTO"].sum()
        
        balance_neto = ingresos - egresos
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Ingresos", f"${ingresos:,.2f}")
        col2.metric("Total Egresos", f"${egresos:,.2f}")
        col3.metric("Balance Neto", f"${balance_neto:,.2f}", delta=f"${balance_neto:,.2f}")
        st.markdown("---")
        
        st.markdown(f"### Historial de Movimientos ({periodo_sel_bal})")
        st.dataframe(df_bal_filtrado.drop(columns=["PERIODO"], errors="ignore"), use_container_width=True)
        
        with st.expander("🗑️ Eliminar Movimiento del Balance (Corrección por Error)"):
            ids_balance_disp = df_bal_filtrado["ID_BALANCE"].tolist() if not df_bal_filtrado.empty else []
            if ids_balance_disp:
                id_bal_a_borrar = st.selectbox("Selecciona el ID_BALANCE a eliminar:", ids_balance_disp, key="del_bal_sel_tab3")
                if st.button("Eliminar del Balance (Supabase)", key="btn_del_bal_tab3"):
                    try:
                        supabase.table("BALANCE").delete().eq("ID_BALANCE", id_bal_a_borrar).execute()
                        st.success(f"¡El registro {id_bal_a_borrar} ha sido eliminado correctamente de Supabase y del Balance!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar de Supabase: {e}")
            else:
                st.info("No hay movimientos en este periodo para eliminar.")
    else:
        st.info("Aún no hay movimientos liquidados que alimenten el balance.")
# ==========================================
# TAB 4: CLIENTES, PROVEEDORES Y CONDUCTORES
# ==========================================
with tab4:
    if "form_cli_key" not in st.session_state:
        st.session_state["form_cli_key"] = 0
    if "form_pro_key" not in st.session_state:
        st.session_state["form_pro_key"] = 0
    if "form_cond_key" not in st.session_state:
        st.session_state["form_cond_key"] = 0

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Catálogo de Clientes")
        df_cli = fetch_table("CLIENTES")
        st.dataframe(df_cli, use_container_width=True)
        
        with st.expander("🗑️ Eliminar Cliente"):
            ids_cli = df_cli["ID_CLIENTE"].tolist() if not df_cli.empty else []
            if ids_cli:
                cli_del = st.selectbox("Selecciona ID de Cliente:", ids_cli, key="del_cli_tab4")
                if st.button("Eliminar Cliente", key="btn_del_cli_tab4"):
                    try:
                        supabase.table("CLIENTES").delete().eq("ID_CLIENTE", cli_del).execute()
                        st.success("Cliente eliminado con éxito.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")
            else:
                st.info("No hay clientes registrados.")
                        
        with st.expander("➕ Agregar Cliente"):
            id_cli_auto = generar_id("CLI")
            with st.form(f"form_cliente_{st.session_state['form_cli_key']}"):
                st.text_input("ID Cliente (Automático)", value=id_cli_auto, disabled=True, key=f"txt_id_cli_{st.session_state['form_cli_key']}")
                nombre_cli = st.text_input("Nombre Comercial", key=f"nom_cli_{st.session_state['form_cli_key']}")
                rep_cli = st.text_input("Representante Legal", key=f"rep_cli_{st.session_state['form_cli_key']}")
                rfc_cli = st.text_input("RFC", key=f"rfc_cli_{st.session_state['form_cli_key']}")
                fecha_alta_cli = st.date_input("Fecha de Alta", key=f"fec_cli_{st.session_state['form_cli_key']}")
                com_cli = st.text_input("Comentarios", key=f"com_cli_{st.session_state['form_cli_key']}")
                
                if st.form_submit_button("Guardar Cliente"):
                    try:
                        supabase.table("CLIENTES").insert({
                            "ID_CLIENTE": id_cli_auto,
                            "NOMBRE_COMERCIAL": nombre_cli,
                            "REP_LEGAL": rep_cli,
                            "RFC": rfc_cli,
                            "FECHA_INGRESO": str(fecha_alta_cli),
                            "COMENTARIOS": com_cli
                        }).execute()
                        st.session_state["form_cli_key"] += 1
                        st.success("¡Cliente guardado exitosamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")
                        
    with col2:
        st.subheader("Catálogo de Proveedores")
        df_pro = fetch_table("PROVEEDORES")
        st.dataframe(df_pro, use_container_width=True)
        
        with st.expander("🗑️ Eliminar Proveedor"):
            ids_pro = df_pro["ID_PROVEEDOR"].tolist() if not df_pro.empty else []
            if ids_pro:
                pro_del = st.selectbox("Selecciona ID de Proveedor:", ids_pro, key="del_pro_tab4")
                if st.button("Eliminar Proveedor", key="btn_del_pro_tab4"):
                    try:
                        supabase.table("PROVEEDORES").delete().eq("ID_PROVEEDOR", pro_del).execute()
                        st.success("Proveedor eliminado con éxito.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")
            else:
                st.info("No hay proveedores registrados.")
                        
        with st.expander("➕ Agregar Proveedor"):
            id_pro_auto = generar_id("PROV")
            with st.form(f"form_proveedor_{st.session_state['form_pro_key']}"):
                st.text_input("ID Proveedor (Automático)", value=id_pro_auto, disabled=True, key=f"txt_id_pro_{st.session_state['form_pro_key']}")
                nombre_pro = st.text_input("Nombre Comercial Proveedor", key=f"nom_pro_{st.session_state['form_pro_key']}")
                rep_pro = st.text_input("Representante Legal", key=f"rep_pro_{st.session_state['form_pro_key']}")
                rfc_pro = st.text_input("RFC", key=f"rfc_pro_{st.session_state['form_pro_key']}")
                fecha_alta_pro = st.date_input("Fecha de Alta", key=f"fec_pro_{st.session_state['form_pro_key']}")
                com_pro = st.text_input("Comentarios", key=f"com_pro_{st.session_state['form_pro_key']}")
                
                if st.form_submit_button("Guardar Proveedor"):
                    try:
                        supabase.table("PROVEEDORES").insert({
                            "ID_PROVEEDOR": id_pro_auto,
                            "NOMBRE_COMERCIAL": nombre_pro,
                            "REP_LEGAL": rep_pro,
                            "RFC": rfc_pro,
                            "FECHA_INGRESO": str(fecha_alta_pro),
                            "COMENTARIOS": com_pro
                        }).execute()
                        st.session_state["form_pro_key"] += 1
                        st.success("¡Proveedor guardado exitosamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

    st.markdown("---")
    st.subheader("🚚 Conductores (Modelo Mixto - Asignados a Proveedores)")
    df_cond = fetch_table("CONDUCTORES")
    df_pro_tabla = fetch_table("PROVEEDORES")
    
    if not df_cond.empty and not df_pro_tabla.empty:
        if "ID_PROVEEDOR" in df_cond.columns and "ID_PROVEEDOR" in df_pro_tabla.columns:
            df_cond = df_cond.merge(
                df_pro_tabla[["ID_PROVEEDOR", "NOMBRE_COMERCIAL"]], 
                on="ID_PROVEEDOR", 
                how="left"
            ).rename(columns={"NOMBRE_COMERCIAL": "PROVEEDOR"})
            
            columnas_orden = [c for c in df_cond.columns if c not in ["ID_PROVEEDOR", "PROVEEDOR"]]
            if "NOMBRE_CONDUCTOR" in columnas_orden:
                idx = columnas_orden.index("NOMBRE_CONDUCTOR") + 1
                columnas_orden.insert(idx, "PROVEEDOR")
            else:
                columnas_orden.append("PROVEEDOR")
            
            df_cond = df_cond[columnas_orden]
            if "ID_PROVEEDOR" in df_cond.columns:
                df_cond = df_cond.drop(columns=["ID_PROVEEDOR"])

    if not df_cond.empty:
        st.dataframe(df_cond, use_container_width=True)
    else:
        st.info("Aún no hay conductores registrados bajo el modelo mixto.")

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        with st.expander("🗑️ Eliminar Conductor"):
            df_cond_del = fetch_table("CONDUCTORES")
            ids_cond = df_cond_del["ID_CONDUCTOR"].tolist() if not df_cond_del.empty else []
            if ids_cond:
                cond_del = st.selectbox("Selecciona ID de Conductor:", ids_cond, key="del_cond_tab4")
                if st.button("Eliminar Conductor", key="btn_del_cond_tab4"):
                    try:
                        supabase.table("CONDUCTORES").delete().eq("ID_CONDUCTOR", cond_del).execute()
                        st.success("Conductor eliminado con éxito.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")
            else:
                st.info("No hay conductores para eliminar.")

    with col_c2:
        with st.expander("➕ Registrar Conductor (Modelo Mixto)"):
            id_cond_auto = generar_id("COND")
            with st.form(f"form_conductor_{st.session_state['form_cond_key']}"):
                st.text_input("ID Conductor (Automático)", value=id_cond_auto, disabled=True, key=f"txt_id_cond_{st.session_state['form_cond_key']}")
                nombre_cond = st.text_input("Nombre Completo del Conductor", key=f"nom_cond_{st.session_state['form_cond_key']}")
                rfc_cond = st.text_input("RFC del Conductor", key=f"rfc_cond_{st.session_state['form_cond_key']}")
                
                df_provs_select = fetch_table("PROVEEDORES")
                if not df_provs_select.empty:
                    mapa_proveedores = dict(zip(df_provs_select["NOMBRE_COMERCIAL"], df_provs_select["ID_PROVEEDOR"]))
                    lista_nombres_prov = list(mapa_proveedores.keys())
                else:
                    mapa_proveedores = {}
                    lista_nombres_prov = []
                
                proveedor_seleccionado_nombre = st.selectbox("Proveedor al que Pertenece", lista_nombres_prov, key=f"prov_asig_{st.session_state['form_cond_key']}")
                fecha_alta_cond = st.date_input("Fecha de Alta", key=f"fec_cond_{st.session_state['form_cond_key']}")
                com_cond = st.text_input("Comentarios / Unidad asignada", key=f"com_cond_{st.session_state['form_cond_key']}")
                
                if st.form_submit_button("Guardar Conductor"):
                    if not lista_nombres_prov:
                        st.error("Debes registrar al menos un proveedor antes de dar de alta conductores.")
                    else:
                        id_proveedor_real = mapa_proveedores.get(proveedor_seleccionado_nombre)
                        try:
                            supabase.table("CONDUCTORES").insert({
                                "ID_CONDUCTOR": id_cond_auto,
                                "NOMBRE_CONDUCTOR": nombre_cond,
                                "RFC_CONDUCTOR": rfc_cond,
                                "ID_PROVEEDOR": id_proveedor_real,
                                "FECHA_ALTA": str(fecha_alta_cond),
                                "COMENTARIOS": com_cond
                            }).execute()
                            st.session_state["form_cond_key"] += 1
                            st.success("¡Conductor registrado y asociado al proveedor exitosamente!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

# ==========================================
# TAB 5: AUDITORÍA DE PENALIZACIONES
# ==========================================
with tab5:
    st.subheader("⚠️ Bitácora y Control de Penalizaciones")
    st.info("💡 Nota: Las penalizaciones operativas ahora se aplican directamente al registrar la deuda en los Tabs 1 y 2 para calcular correctamente el neto fiscal e IVA. Este módulo sirve como bitácora de consulta y registro histórico.")
    
    tipo_penalizacion_vista = st.radio(
        "Selecciona el tipo de penalización:", 
        ["Penalizaciones del Cliente hacia Mí", "Penalizaciones mías hacia el Proveedor"],
        horizontal=True,
        key="radio_tipo_pen"
    )
    
    st.markdown("---")
    df_pen = fetch_table("PENALIZACIONES")
    df_cli_pen = fetch_table("CLIENTES")
    df_prov_pen = fetch_table("PROVEEDORES")
    
    if tipo_penalizacion_vista == "Penalizaciones del Cliente hacia Mí":
        st.markdown("### 🏢 Bitácora de Penalizaciones por Clientes")
        
        if not df_pen.empty and "TIPO_ENTIDAD" in df_pen.columns:
            df_pen_cli = df_pen[df_pen["TIPO_ENTIDAD"] == "CLIENTE"].copy()
        else:
            df_pen_cli = pd.DataFrame()
            
        if not df_pen_cli.empty and "FECHA" in df_pen_cli.columns:
            df_pen_cli["PERIODO"] = pd.to_datetime(df_pen_cli["FECHA"], errors='coerce').dt.strftime('%Y-%m')
            per_pen_c = ["Todos"] + sorted(df_pen_cli["PERIODO"].dropna().unique().tolist(), reverse=True)
            sel_per_pc = st.selectbox("Filtrar por Periodo (Mes):", per_pen_c, key="per_pen_cli")
            
            df_pen_cli_filt = df_pen_cli.copy()
            if sel_per_pc != "Todos":
                df_pen_cli_filt = df_pen_cli_filt[df_pen_cli_filt["PERIODO"] == sel_per_pc]
                
            st.dataframe(df_pen_cli_filt.drop(columns=["PERIODO"], errors="ignore"), use_container_width=True)
            
            with st.expander("🗑️ Eliminar Registro de Penalización de Cliente"):
                ids_pc = df_pen_cli_filt["ID_PENALIZACION"].tolist() if not df_pen_cli_filt.empty else []
                if ids_pc:
                    id_del_pc = st.selectbox("Selecciona ID a eliminar:", ids_pc, key="del_pc_sel")
                    if st.button("Eliminar Registro", key="btn_del_pc"):
                        try:
                            supabase.table("PENALIZACIONES").delete().eq("ID_PENALIZACION", id_del_pc).execute()
                            st.success("Registro eliminado con éxito.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar: {e}")
        else:
            st.info("No hay registros de penalizaciones de clientes.")
            
        with st.expander("➕ Registrar Penalización Histórica (Solo Bitácora)"):
            id_pen_c_auto = generar_id("PEN-CLI")
            with st.form("form_pen_cliente"):
                st.text_input("ID Penalización", value=id_pen_c_auto, disabled=True)
                
                mapa_cli_p = dict(zip(df_cli_pen["NOMBRE_COMERCIAL"], df_cli_pen["ID_CLIENTE"])) if not df_cli_pen.empty else {}
                lista_n_cli = list(mapa_cli_p.keys())
                cli_sel_pen = st.selectbox("Cliente", lista_n_cli)
                
                fec_pen_c = st.date_input("Fecha", key="fec_pc")
                motivo_pen_c = st.text_area("Motivo / Detalle", key="mot_pc")
                monto_pen_c = st.number_input("Monto ($)", min_value=0.0, format="%.2f", key="mnt_pc")
                
                if st.form_submit_button("Guardar en Bitácora"):
                    if not lista_n_cli:
                        st.error("Registra clientes primero.")
                    else:
                        id_cli_real = mapa_cli_p.get(cli_sel_pen)
                        try:
                            supabase.table("PENALIZACIONES").insert({
                                "ID_PENALIZACION": id_pen_c_auto,
                                "TIPO_ENTIDAD": "CLIENTE",
                                "ID_AFECTADO": id_cli_real,
                                "FECHA": str(fec_pen_c),
                                "MOTIVO": motivo_pen_c,
                                "MONTO": monto_pen_c
                            }).execute()
                            st.success("¡Registrado en bitácora correctamente!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")
                            
    else:
        st.markdown("### 🚛 Bitácora de Penalizaciones a Proveedores")
        
        if not df_pen.empty and "TIPO_ENTIDAD" in df_pen.columns:
            df_pen_prov = df_pen[df_pen["TIPO_ENTIDAD"] == "PROVEEDOR"].copy()
        else:
            df_pen_prov = pd.DataFrame()
            
        if not df_pen_prov.empty and "FECHA" in df_pen_prov.columns:
            df_pen_prov["PERIODO"] = pd.to_datetime(df_pen_prov["FECHA"], errors='coerce').dt.strftime('%Y-%m')
            per_pen_p = ["Todos"] + sorted(df_pen_prov["PERIODO"].dropna().unique().tolist(), reverse=True)
            sel_per_pp = st.selectbox("Filtrar por Periodo (Mes):", per_pen_p, key="per_pen_prov")
            
            df_pen_prov_filt = df_pen_prov.copy()
            if sel_per_pp != "Todos":
                df_pen_prov_filt = df_pen_prov_filt[df_pen_prov_filt["PERIODO"] == sel_per_pp]
                
            st.dataframe(df_pen_prov_filt.drop(columns=["PERIODO"], errors="ignore"), use_container_width=True)
            
            with st.expander("🗑️ Eliminar Registro de Penalización a Proveedor"):
                ids_pp = df_pen_prov_filt["ID_PENALIZACION"].tolist() if not df_pen_prov_filt.empty else []
                if ids_pp:
                    id_del_pp = st.selectbox("Selecciona ID a eliminar:", ids_pp, key="del_pp_sel")
                    if st.button("Eliminar Registro", key="btn_del_pp"):
                        try:
                            supabase.table("PENALIZACIONES").delete().eq("ID_PENALIZACION", id_del_pp).execute()
                            st.success("Registro eliminado con éxito.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar: {e}")
        else:
            st.info("No hay registros de penalizaciones a proveedores.")
            
        with st.expander("➕ Registrar Penalización Histórica (Solo Bitácora)"):
            id_pen_p_auto = generar_id("PEN-PROV")
            with st.form("form_pen_proveedor"):
                st.text_input("ID Penalización", value=id_pen_p_auto, disabled=True)
                
                mapa_prov_p = dict(zip(df_prov_pen["NOMBRE_COMERCIAL"], df_prov_pen["ID_PROVEEDOR"])) if not df_prov_pen.empty else {}
                lista_n_prov = list(mapa_prov_p.keys())
                prov_sel_pen = st.selectbox("Proveedor", lista_n_prov)
                
                fec_pen_p = st.date_input("Fecha", key="fec_pp")
                motivo_pen_p = st.text_area("Motivo / Detalle", key="mot_pp")
                monto_pen_p = st.number_input("Monto ($)", min_value=0.0, format="%.2f", key="mnt_pp")
                
                if st.form_submit_button("Guardar en Bitácora"):
                    if not lista_n_prov:
                        st.error("Registra proveedores primero.")
                    else:
                        id_prov_real = mapa_prov_p.get(prov_sel_pen)
                        try:
                            supabase.table("PENALIZACIONES").insert({
                                "ID_PENALIZACION": id_pen_p_auto,
                                "TIPO_ENTIDAD": "PROVEEDOR",
                                "ID_AFECTADO": id_prov_real,
                                "FECHA": str(fec_pen_p),
                                "MOTIVO": motivo_pen_p,
                                "MONTO": monto_pen_p
                            }).execute()
                            st.success("¡Registrado en bitácora correctamente!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")
