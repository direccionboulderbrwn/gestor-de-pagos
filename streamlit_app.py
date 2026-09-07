import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import uuid
import requests
import base64
import json

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

# ==========================================
# NUEVAS FUNCIONES BACKEND PARA GESTIÓN DE NOTAS EN GITHUB
# ==========================================
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
except Exception:
    GITHUB_TOKEN = None

try:
    GITHUB_REPO = st.secrets["github"]["repo"]
except Exception:
    GITHUB_REPO = None

FILE_PATH = "data/notas.json"

def github_api_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

def obtener_notas_github():
    """Consulta la versión actual de data/notas.json en GitHub y retorna la lista de notas y el SHA."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return [], None
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE_PATH}"
    try:
        response = requests.get(url, headers=github_api_headers())
        if response.status_code == 200:
            file_data = response.json()
            sha = file_data["sha"]
            content_bytes = base64.b64decode(file_data["content"])
            notas = json.loads(content_bytes.decode("utf-8"))
            return notas, sha
        elif response.status_code == 404:
            return [], None
        else:
            return [], None
    except Exception:
        return [], None

def guardar_notas_github(notas, sha, mensaje_commit):
    """Actualiza data/notas.json en GitHub usando el SHA correspondiente y generando un commit descriptivo."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        st.error("No se han configurado las credenciales de GitHub en los Secrets.")
        return False
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE_PATH}"
    content_str = json.dumps(notas, indent=4, ensure_ascii=False)
    content_encoded = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
    payload = {
        "message": mensaje_commit,
        "content": content_encoded
    }
    if sha:
        payload["sha"] = sha
    try:
        response = requests.put(url, headers=github_api_headers(), json=payload)
        return response.status_code in [200, 201]
    except Exception:
        return False


# --- TÍTULO PRINCIPAL ---
st.title("📊 Control Operativo y Financiero - TEN")
st.markdown("---")

# Pestañas principales de navegación
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Deudas por Cobrar", 
    "Deudas por Pagar", 
    "Balance Automático", 
    "Clientes y Proveedores", 
    "Resumen General", 
    "Notas y Anotaciones"
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
        
    with st.expander("➕ Registrar Nueva Deuda por Cobrar (Con Penalización, IVA y Retenciones RESICO)"):
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
            st.markdown("##### 🧮 Cálculo de Importes, Penalizaciones y Tasas Fiscales")
            monto_base = st.number_input("Monto Base / Subtotal Factura ($)", min_value=0.0, format="%.2f", key="val_base_cxc")
            
            aplica_pen_cli = st.checkbox("¿El cliente aplicó una o varias penalizaciones a este monto?", key="chk_pen_cli")
            monto_penalizacion = st.number_input("Monto Total de las Penalizaciones ($)", min_value=0.0, format="%.2f", key="val_pen_cli")
            motivos_multiples = st.text_area("Desglose de Motivos de Penalización", key="mot_pen_cli_mult")
            
            col_imp1, col_imp2, col_imp3 = st.columns(3)
            with col_imp1:
                aplicar_iva = st.checkbox("Agregar IVA (16%)", value=True, key="chk_iva_cxc")
            with col_imp2:
                aplicar_resico_isr = st.checkbox("Retención ISR RESICO (1.25%)", value=False, key="chk_resico_isr_cxc")
            with col_imp3:
                tipo_ret_iva = st.selectbox("Retención IVA", ["Sin Retención", "4% (Fletes/Autotransporte)", "10.66% (2/3 IVA RESICO/Honorarios)"], key="sel_ret_iva_cxc")
                
            concepto = st.text_area("Concepto / Detalle general de la Operación", key="con_cxc_form")
            
            # --- CÁLCULO FINANCIERO Y FISCAL ---
            penalizacion_real = monto_penalizacion if aplica_pen_cli else 0.0
            subtotal_neto = max(0.0, monto_base - penalizacion_real)
            
            iva_monto = subtotal_neto * 0.16 if aplicar_iva else 0.0
            ret_isr = subtotal_neto * 0.0125 if aplicar_resico_isr else 0.0
            
            if tipo_ret_iva == "4% (Fletes/Autotransporte)":
                ret_iva = subtotal_neto * 0.04
            elif tipo_ret_iva == "10.66% (2/3 IVA RESICO/Honorarios)":
                ret_iva = subtotal_neto * (2/3 * 0.16)
            else:
                ret_iva = 0.0
                
            monto_final_neto = subtotal_neto + iva_monto - ret_isr - ret_iva
            
            st.info(f"💡 Subtotal Neto: **${subtotal_neto:,.2f}** | IVA: **${iva_monto:,.2f}** | Ret. ISR (1.25%): **-${ret_isr:,.2f}** | Ret. IVA: **-${ret_iva:,.2f}** | **Monto Final: ${monto_final_neto:,.2f}**")
            
            if st.form_submit_button("Guardar Deuda con Desglose Fiscal"):
                if not lista_nombres_cli:
                    st.error("Primero debes registrar clientes en el Catálogo.")
                else:
                    id_cli_real = mapa_clis.get(cliente_nombre_sel)
                    try:
                        detalle_completo = f"{concepto} | Subtotal: ${monto_base:,.2f}"
                        if aplica_pen_cli and penalizacion_real > 0:
                            detalle_completo += f" | Total Penalizaciones (${penalizacion_real:,.2f}): {motivos_multiples}"
                        if aplicar_resico_isr:
                            detalle_completo += f" | Ret. ISR 1.25%"
                        if ret_iva > 0:
                            detalle_completo += f" | Ret. IVA ({tipo_ret_iva})"

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
                            
                        st.success("¡Deuda registrada con cálculo fiscal exacto!")
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
            
            aplica_pen_prov = st.checkbox("¿Le apliqué una o varias penalizaciones o descuentos a este proveedor?", key="chk_pen_prov")
            monto_penalizacion_p = st.number_input("Monto Total de las Penalizaciones ($)", min_value=0.0, format="%.2f", key="val_pen_prov")
            motivos_multiples_p = st.text_area("Desglose de Motivos de Penalización al Proveedor", key="mot_pen_prov_mult")
            
            col_imp1_p, col_imp2_p, col_imp3_p = st.columns(3)
            with col_imp1_p:
                aplicar_iva_p = st.checkbox("Agregar IVA (16%)", value=True, key="chk_iva_cxp")
            with col_imp2_p:
                aplicar_resico_isr_p = st.checkbox("Retención ISR RESICO (1.25%)", value=False, key="chk_resico_isr_cxp")
            with col_imp3_p:
                tipo_ret_iva_p = st.selectbox("Retención IVA", ["Sin Retención", "4% (Fletes/Autotransporte)", "10.66% (2/3 IVA RESICO/Honorarios)"], key="sel_ret_iva_cxp")
                
            concepto_p = st.text_area("Concepto / Detalle general", key="con_cxp_form")
            
            # --- CÁLCULO FINANCIERO Y FISCAL ---
            penalizacion_real_p = monto_penalizacion_p if aplica_pen_prov else 0.0
            subtotal_neto_p = max(0.0, monto_base_p - penalizacion_real_p)
            
            iva_monto_p = subtotal_neto_p * 0.16 if aplicar_iva_p else 0.0
            ret_isr_p = subtotal_neto_p * 0.0125 if aplicar_resico_isr_p else 0.0
            
            if tipo_ret_iva_p == "4% (Fletes/Autotransporte)":
                ret_iva_p = subtotal_neto_p * 0.04
            elif tipo_ret_iva_p == "10.66% (2/3 IVA RESICO/Honorarios)":
                ret_iva_p = subtotal_neto_p * (2/3 * 0.16)
            else:
                ret_iva_p = 0.0
                
            monto_final_neto_p = subtotal_neto_p + iva_monto_p - ret_isr_p - ret_iva_p
            
            st.info(f"💡 Subtotal Neto a Pagar: **${subtotal_neto_p:,.2f}** | IVA: **${iva_monto_p:,.2f}** | Ret. ISR (1.25%): **-${ret_isr_p:,.2f}** | Ret. IVA: **-${ret_iva_p:,.2f}** | **Total Final Neto: ${monto_final_neto_p:,.2f}**")
            
            if st.form_submit_button("Guardar Deuda por Pagar"):
                if not lista_nombres_p:
                    st.error("Primero debes registrar proveedores en el Catálogo.")
                else:
                    id_prov_real = mapa_provs.get(proveedor_nombre_sel)
                    try:
                        detalle_completo_p = f"{concepto_p} | Subtotal: ${monto_base_p:,.2f}"
                        if aplica_pen_prov and penalizacion_real_p > 0:
                            detalle_completo_p += f" | Total Penalizaciones al proveedor (${penalizacion_real_p:,.2f}): {motivos_multiples_p}"
                        if aplicar_resico_isr_p:
                            detalle_completo_p += f" | Ret. ISR 1.25%"
                        if ret_iva_p > 0:
                            detalle_completo_p += f" | Ret. IVA ({tipo_ret_iva_p})"

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
# TAB 3: BALANCE AUTOMÁTICO (Consistente con Penalizaciones Netas)
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
# TAB 5: 📊 RESUMEN GENERAL (REPORTES Y CONCILIACIÓN)
# ==========================================
with tab5:
    st.subheader("📊 Resumen General y Reportes Financieros")
    st.info("💡 Este módulo concentra la auditoría de penalizaciones, el resumen de pagos por proveedor, la consolidación de ingresos/egresos, la nómina por driver y la proyección financiera al cierre.")

    # --- FILTROS GLOBALES PARA EL RESUMEN GENERAL ---
    st.markdown("### 🔍 Filtros Globales de Análisis")
    df_cxc_rg = fetch_table("DEUDAS_X_COBRAR")
    df_cxp_rg = fetch_table("DEUDA_X_PAGAR")
    df_bal_rg = fetch_table("BALANCE")
    df_cond_rg = fetch_table("CONDUCTORES")
    df_prov_rg = fetch_table("PROVEEDORES")
    df_cli_rg = fetch_table("CLIENTES")

    # Extraer periodos disponibles de las fuentes principales
    periodos_disponibles_rg = ["Todos"]
    all_dates = []
    for df_temp in [df_cxc_rg, df_cxp_rg, df_bal_rg]:
        if not df_temp.empty:
            for col_f in ["FECHA_OPERACION", "FECHA"]:
                if col_f in df_temp.columns:
                    fechas_parsed = pd.to_datetime(df_temp[col_f], errors='coerce').dt.strftime('%Y-%m')
                    all_dates.extend(fechas_parsed.dropna().unique().tolist())
    
    if all_dates:
        periodos_disponibles_rg = ["Todos"] + sorted(list(set(all_dates)), reverse=True)

    col_rg1, col_rg2 = st.columns(2)
    with col_rg1:
        filtro_periodo_rg = st.selectbox("Filtrar por Periodo (Mes):", periodos_disponibles_rg, key="rg_filtro_periodo")
    with col_rg2:
        lista_prov_filtro = ["Todos"] + (df_prov_rg["NOMBRE_COMERCIAL"].tolist() if not df_prov_rg.empty and "NOMBRE_COMERCIAL" in df_prov_rg.columns else [])
        filtro_prov_rg = st.selectbox("Filtrar por Proveedor:", lista_prov_filtro, key="rg_filtro_proveedor")

    st.markdown("---")

    # ==========================================
    # 1. BLOQUE DE INDICADORES FINANCIEROS (REAL ACTUAL)
    # ==========================================
    st.markdown("### 📈 Indicadores Financieros del Periodo (Real Actual)")
    
    df_bal_filtrado_rg = df_bal_rg.copy()
    if not df_bal_filtrado_rg.empty and "FECHA" in df_bal_filtrado_rg.columns:
        df_bal_filtrado_rg["PERIODO"] = pd.to_datetime(df_bal_filtrado_rg["FECHA"], errors='coerce').dt.strftime('%Y-%m')
        if filtro_periodo_rg != "Todos":
            df_bal_filtrado_rg = df_bal_filtrado_rg[df_bal_filtrado_rg["PERIODO"] == filtro_periodo_rg]

    total_ingresos_rg = df_bal_filtrado_rg[df_bal_filtrado_rg["TIPO"].str.contains("Ingreso|Cobro", case=False, na=False)]["MONTO"].sum() if not df_bal_filtrado_rg.empty else 0.0
    total_egresos_rg = df_bal_filtrado_rg[df_bal_filtrado_rg["TIPO"].str.contains("Egreso|Pago", case=False, na=False)]["MONTO"].sum() if not df_bal_filtrado_rg.empty else 0.0
    
    # Extracción de penalizaciones globales desde los conceptos de CXC y CXP
    total_pen_clientes = 0.0
    if not df_cxc_rg.empty and "CONCEPTO" in df_cxc_rg.columns:
        import re
        def extraer_monto_gen(texto):
            match = re.search(r"Penalizaciones\s*\(\$(\d[\d,]*\.?\d*)\)", str(texto))
            return float(match.group(1).replace(",", "")) if match else 0.0
        total_pen_clientes = df_cxc_rg["CONCEPTO"].apply(extraer_monto_gen).sum()

    total_pen_proveedores = 0.0
    if not df_cxp_rg.empty and "CONCEPTO" in df_cxp_rg.columns:
        def extraer_monto_gen_p(texto):
            match = re.search(r"Penalizaciones.*?\(\$(\d[\d,]*\.?\d*)\)", str(texto))
            return float(match.group(1).replace(",", "")) if match else 0.0
        total_pen_proveedores = df_cxp_rg["CONCEPTO"].apply(extraer_monto_gen_p).sum()

    total_penalizaciones_rg = total_pen_clientes + total_pen_proveedores
    balance_neto_rg = total_ingresos_rg - total_egresos_rg

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("Total Ingresos", f"${total_ingresos_rg:,.2f}")
    kpi2.metric("Total Egresos", f"${total_egresos_rg:,.2f}")
    kpi3.metric("Total Penalizaciones", f"${total_penalizaciones_rg:,.2f}")
    kpi4.metric("Pago Proveedores / Nómina", f"${total_egresos_rg:,.2f}")
    kpi5.metric("Balance Neto", f"${balance_neto_rg:,.2f}", delta=f"${balance_neto_rg:,.2f}")

    st.markdown("---")

    # ==========================================
    # NUEVA SECCIÓN: PROYECCIÓN FINANCIERA AL CIERRE
    # ==========================================
    st.markdown("### 📈 Proyección Financiera al CIERRE")
    
    # Calcular Pendiente por Cobrar desde TAB 1 (DEUDAS_X_COBRAR con estatus Pendiente o Parcial)
    pendiente_cobrar = 0.0
    if not df_cxc_rg.empty and "ESTATUS" in df_cxc_rg.columns and "VALOR" in df_cxc_rg.columns:
        df_cxc_rg["PERIODO"] = pd.to_datetime(df_cxc_rg["FECHA_OPERACION"], errors='coerce').dt.strftime('%Y-%m')
        df_cxc_pend = df_cxc_rg[df_cxc_rg["ESTATUS"].isin(["Pendiente", "Parcial"])].copy()
        if filtro_periodo_rg != "Todos":
            df_cxc_pend = df_cxc_pend[df_cxc_pend["PERIODO"] == filtro_periodo_rg]
        pendiente_cobrar = df_cxc_pend["VALOR"].sum()

    # Calcular Pendiente por Pagar desde TAB 2 (DEUDA_X_PAGAR con estatus Pendiente o Parcial)
    pendiente_pagar = 0.0
    if not df_cxp_rg.empty and "ESTATUS" in df_cxp_rg.columns and "VALOR" in df_cxp_rg.columns:
        df_cxp_rg["PERIODO"] = pd.to_datetime(df_cxp_rg["FECHA_OPERACION"], errors='coerce').dt.strftime('%Y-%m')
        df_cxp_pend = df_cxp_rg[df_cxp_rg["ESTATUS"].isin(["Pendiente", "Parcial"])].copy()
        if filtro_periodo_rg != "Todos":
            df_cxp_pend = df_cxp_pend[df_cxp_pend["PERIODO"] == filtro_periodo_rg]
        if filtro_prov_rg != "Todos" and "NOMBRE_PROVEEDOR" in df_cxp_pend.columns:
            df_cxp_pend = df_cxp_pend[df_cxp_pend["NOMBRE_PROVEEDOR"] == filtro_prov_rg]
        pendiente_pagar = df_cxp_pend["VALOR"].sum()

    ingreso_proyectado = total_ingresos_rg + pendiente_cobrar
    egreso_proyectado = total_egresos_rg + pendiente_pagar
    balance_proyectado = ingreso_proyectado - egreso_proyectado
    variacion_esperada = balance_proyectado - balance_neto_rg

    # Formateo visual con signo para la variación esperada
    if variacion_esperada > 0:
        var_str = f"+${variacion_esperada:,.2f}"
    elif variacion_esperada < 0:
        var_str = f"-${abs(variacion_esperada):,.2f}"
    else:
        var_str = "$0.00"

    # Fila 1 de Proyecciones
    p1, p2, p3 = st.columns(3)
    p1.metric("💰 Pendiente por Cobrar", f"${pendiente_cobrar:,.2f}")
    p2.metric("💸 Pendiente por Pagar", f"${pendiente_pagar:,.2f}")
    p3.metric("📊 Ingreso Proyectado al Cierre", f"${ingreso_proyectado:,.2f}")

    # Fila 2 de Proyecciones
    p4, p5, p6 = st.columns(3)
    p4.metric("📊 Egreso Proyectado al Cierre", f"${egreso_proyectado:,.2f}")
    p5.metric("🎯 Balance Proyectado al Cierre", f"${balance_proyectado:,.2f}", delta=f"${balance_proyectado:,.2f}")
    p6.metric("📈 Variación Esperada al Cierre", var_str, delta=var_str)

    st.markdown("---")

    # ==========================================
    # 2. BLOQUE DE PENALIZACIONES (Detalle actual conservado)
    # ==========================================
    st.markdown("### ⚠️ Detalle y Costo Neto de Penalizaciones")
    
    tipo_penalizacion_vista = st.radio(
        "Selecciona el tipo de penalización a auditar:", 
        ["Penalizaciones del Cliente hacia Mí", "Penalizaciones mías hacia el Proveedor"],
        horizontal=True,
        key="radio_tipo_pen_rg"
    )

    if tipo_penalizacion_vista == "Penalizaciones del Cliente hacia Mí":
        if not df_cxc_rg.empty and not df_cli_rg.empty and "NOMBRE_COMERCIAL" not in df_cxc_rg.columns:
            df_cxc_rg = df_cxc_rg.merge(df_cli_rg[["ID_CLIENTE", "NOMBRE_COMERCIAL"]], left_on="CLIENTE", right_on="ID_CLIENTE", how="left").rename(columns={"NOMBRE_COMERCIAL": "NOMBRE_CLIENTE"})
        
        if not df_cxc_rg.empty and "CONCEPTO" in df_cxc_rg.columns:
            df_pen_cxc_rg = df_cxc_rg[df_cxc_rg["CONCEPTO"].str.contains("Penalización|Total Penalizaciones", case=False, na=False)].copy()
            if not df_pen_cxc_rg.empty:
                df_pen_cxc_rg["MONTO_NETO_PENALIZACION"] = df_pen_cxc_rg["CONCEPTO"].apply(lambda x: extraer_monto_gen(x))
                df_pen_cxc_rg["PERIODO"] = pd.to_datetime(df_pen_cxc_rg["FECHA_OPERACION"], errors='coerce').dt.strftime('%Y-%m')
                
                if filtro_periodo_rg != "Todos":
                    df_pen_cxc_rg = df_pen_cxc_rg[df_pen_cxc_rg["PERIODO"] == filtro_periodo_rg]
                
                st.dataframe(df_pen_cxc_rg[["ID_MOVIMIENTO", "FECHA_OPERACION", "NOMBRE_CLIENTE", "ESTATUS", "MONTO_NETO_PENALIZACION", "CONCEPTO"]], use_container_width=True)
            else:
                st.info("No hay penalizaciones de clientes registradas con los filtros actuales.")
    else:
        if not df_cxp_rg.empty and not df_prov_rg.empty and "NOMBRE_PROVEEDOR" not in df_cxp_rg.columns:
            df_cxp_rg = df_cxp_rg.merge(df_prov_rg[["ID_PROVEEDOR", "NOMBRE_COMERCIAL"]], left_on="PROVEEDOR", right_on="ID_PROVEEDOR", how="left").rename(columns={"NOMBRE_COMERCIAL": "NOMBRE_PROVEEDOR"})
        
        if not df_cxp_rg.empty and "CONCEPTO" in df_cxp_rg.columns:
            df_pen_cxp_rg = df_cxp_rg[df_cxp_rg["CONCEPTO"].str.contains("Penalización|Menos Penalización|Descuento", case=False, na=False)].copy()
            if not df_pen_cxp_rg.empty:
                df_pen_cxp_rg["MONTO_NETO_PENALIZACION"] = df_pen_cxp_rg["CONCEPTO"].apply(lambda x: extraer_monto_gen_p(x))
                df_pen_cxp_rg["PERIODO"] = pd.to_datetime(df_pen_cxp_rg["FECHA_OPERACION"], errors='coerce').dt.strftime('%Y-%m')
                
                if filtro_periodo_rg != "Todos":
                    df_pen_cxp_rg = df_pen_cxp_rg[df_pen_cxp_rg["PERIODO"] == filtro_periodo_rg]
                
                st.dataframe(df_pen_cxp_rg[["ID_MOVIMIENTO", "FECHA_OPERACION", "NOMBRE_PROVEEDOR", "ESTATUS", "MONTO_NETO_PENALIZACION", "CONCEPTO"]], use_container_width=True)
            else:
                st.info("No hay penalizaciones a proveedores registradas con los filtros actuales.")

    st.markdown("---")

    # ==========================================
    # 3. RESUMEN DE PAGO POR PROVEEDOR
    # ==========================================
    st.markdown("### 🏢 Resumen de Pago por Proveedor")
    if not df_cxp_rg.empty and not df_prov_rg.empty:
        if "NOMBRE_PROVEEDOR" not in df_cxp_rg.columns:
            df_cxp_rg = df_cxp_rg.merge(df_prov_rg[["ID_PROVEEDOR", "NOMBRE_COMERCIAL"]], left_on="PROVEEDOR", right_on="ID_PROVEEDOR", how="left").rename(columns={"NOMBRE_COMERCIAL": "NOMBRE_PROVEEDOR"})
        
        df_cxp_rg["PERIODO"] = pd.to_datetime(df_cxp_rg["FECHA_OPERACION"], errors='coerce').dt.strftime('%Y-%m')
        df_prov_resumen = df_cxp_rg.copy()
        
        if filtro_periodo_rg != "Todos":
            df_prov_resumen = df_prov_resumen[df_prov_resumen["PERIODO"] == filtro_periodo_rg]
        if filtro_prov_rg != "Todos":
            df_prov_resumen = df_prov_resumen[df_prov_resumen["NOMBRE_PROVEEDOR"] == filtro_prov_rg]

        if not df_prov_resumen.empty:
            resumen_prov = df_prov_resumen.groupby("NOMBRE_PROVEEDOR").agg(
                Servicios_Generados=("VALOR", "sum"),
                Egresos_Pagados=("VALOR", lambda x: x[df_prov_resumen.loc[x.index, "ESTATUS"] == "Pagado"].sum()),
                Pago_Neto=("VALOR", "sum"),
                Periodo=("PERIODO", "first")
            ).reset_index()
            
            st.dataframe(resumen_prov, use_container_width=True)
        else:
            st.info("No hay información de proveedores para el filtro seleccionado.")
    else:
        st.info("No hay datos suficientes de cuentas por pagar a proveedores.")

    st.markdown("---")

    # ==========================================
    # 4. RESUMEN DE NÓMINA POR DRIVER
    # ==========================================
    st.markdown("### 🚚 Resumen de Nómina por Driver")
    df_bal_cond = fetch_table("BALANCE")
    if not df_cond_rg.empty and not df_prov_rg.empty:
        df_cond_rg = df_cond_rg.merge(df_prov_rg[["ID_PROVEEDOR", "NOMBRE_COMERCIAL"]], on="ID_PROVEEDOR", how="left").rename(columns={"NOMBRE_COMERCIAL": "PROVEEDOR_ASOCIADO"})
        
        if not df_bal_cond.empty:
            pagos_drivers = df_bal_cond[df_bal_cond["TIPO"].str.contains("Pago Conductor", case=False, na=False)].copy()
            pagos_drivers["PERIODO"] = pd.to_datetime(pagos_drivers["FECHA"], errors='coerce').dt.strftime('%Y-%m')
            
            if filtro_periodo_rg != "Todos":
                pagos_drivers = pagos_drivers[pagos_drivers["PERIODO"] == filtro_periodo_rg]
                
            if not pagos_drivers.empty:
                st.dataframe(pagos_drivers[["ID_BALANCE", "FECHA", "CONCEPTO / DETALLE", "MONTO"]], use_container_width=True)
            else:
                st.info("No hay pagos a drivers registrados en este periodo.")
        else:
            st.info("No hay movimientos en el balance.")
    else:
        st.info("No hay conductores registrados en el sistema.")

# ==========================================
# TAB 6: 📝 NOTAS Y ANOTACIONES (GitHub Backend)
# ==========================================
with tab6:
    st.subheader("📝 Notas y Anotaciones (Gestión en Repositorio GitHub)")
    st.info("💡 Este módulo almacena y sincroniza las anotaciones directamente en el archivo `data/notas.json` de tu repositorio mediante commits seguros.")

    if not GITHUB_TOKEN or not GITHUB_REPO:
        st.warning("⚠️ Para utilizar este módulo, configura tus secretos de GitHub (`token` y `repo`) en el panel de Streamlit Cloud.")
    else:
        if "editando_nota_id" not in st.session_state:
            st.session_state["editando_nota_id"] = None

        notas_actuales, file_sha = obtener_notas_github()

        es_edicion = st.session_state["editando_nota_id"] is not None
        nota_a_editar = next((n for n in notas_actuales if n["id"] == st.session_state["editando_nota_id"]), None) if es_edicion else None

        with st.form("form_gestion_notas"):
            st.markdown(f"### {'✏️ Editar Nota' if es_edicion else '➕ Nueva Anotación'}")
            
            titulo_input = st.text_input("Título", value=nota_a_editar["titulo"] if nota_a_editar else "")
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                if nota_a_editar and "fecha_creacion" in nota_a_editar:
                    try:
                        fecha_default = datetime.strptime(nota_a_editar["fecha_creacion"], "%Y-%m-%d").date()
                    except Exception:
                        fecha_default = datetime.today().date()
                else:
                    fecha_default = datetime.today().date()
                
                fecha_input = st.date_input("Fecha", value=fecha_default)
            with col_f2:
                categorias_sugeridas = ["Operativo", "Financiero", "Proveedores", "Clientes", "General", "Urgente"]
                categoria_input = st.selectbox("Categoría", categorias_sugeridas, index=0)
                cat_custom = st.text_input("O escribe otra categoría (opcional)", value="")
                if cat_custom.strip():
                    categoria_input = cat_custom.strip()

            descripcion_input = st.text_area("Descripción", value=nota_a_editar["descripcion"] if nota_a_editar else "")

            btn_texto = "Actualizar Nota" if es_edicion else "Guardar Nota"
            submitted = st.form_submit_button(btn_texto)

            if submitted:
                if not titulo_input.strip() or not descripcion_input.strip():
                    st.error("El título y la descripción son obligatorios.")
                else:
                    timestamp_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    if es_edicion:
                        for n in notas_actuales:
                            if n["id"] == st.session_state["editando_nota_id"]:
                                n["titulo"] = titulo_input
                                n["fecha_creacion"] = str(fecha_input)
                                n["fecha_modificacion"] = timestamp_actual
                                n["categoria"] = categoria_input
                                n["descripcion"] = descripcion_input
                        
                        mensaje_commit = f"Actualizar nota: {titulo_input}"
                        exito = guardar_notas_github(notas_actuales, file_sha, mensaje_commit)
                        if exito:
                            st.success("¡Nota actualizada con éxito en GitHub!")
                            st.session_state["editando_nota_id"] = None
                            st.rerun()
                    else:
                        nuevo_id = generar_id("NOTA")
                        nueva_nota = {
                            "id": nuevo_id,
                            "fecha_creacion": str(fecha_input),
                            "fecha_modificacion": timestamp_actual,
                            "titulo": titulo_input,
                            "categoria": categoria_input,
                            "descripcion": descripcion_input
                        }
                        notas_actuales.append(nueva_nota)
                        
                        mensaje_commit = f"Agregar nota: {titulo_input}"
                        exito = guardar_notas_github(notas_actuales, file_sha, mensaje_commit)
                        if exito:
                            st.success("¡Nota guardada con éxito en GitHub!")
                            st.rerun()

        if es_edicion:
            if st.button("Cancelar Edición"):
                st.session_state["editando_nota_id"] = None
                st.rerun()

        st.markdown("---")
        st.markdown("### 📚 Anotaciones Registradas")

        if not notas_actuales:
            st.info("No hay notas registradas en el repositorio (`data/notas.json`).")
        else:
            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1:
                busqueda = st.text_input("🔍 Buscar en notas (Título o Descripción):", value="")
            with col_b2:
                cats_disponibles = ["Todas"] + sorted(list(set(n.get("categoria", "General") for n in notas_actuales)))
                filtro_cat = st.selectbox("Filtrar por Categoría:", cats_disponibles)
            with col_b3:
                fechas_disp = ["Todas"] + sorted(list(set(n.get("fecha_creacion", "") for n in notas_actuales)), reverse=True)
                filtro_fec = st.selectbox("Filtrar por Fecha:", fechas_disp)

            notas_filtradas = notas_actuales.copy()
            if busqueda.strip():
                q = busqueda.lower()
                notas_filtradas = [n for n in notas_filtradas if q in n["titulo"].lower() or q in n["descripcion"].lower()]
            if filtro_cat != "Todas":
                notas_filtradas = [n for n in notas_filtradas if n.get("categoria") == filtro_cat]
            if filtro_fec != "Todas":
                notas_filtradas = [n for n in notas_filtradas if n.get("fecha_creacion") == filtro_fec]

            st.markdown(f"Mostrando **{len(notas_filtradas)}** de **{len(notas_actuales)}** notas.")

            for nota in notas_filtradas:
                with st.expander(f"📌 [{nota.get('categoria', 'General')}] {nota.get('titulo', 'Sin título')} — *(Creada: {nota.get('fecha_creacion')})*"):
                    st.write(f"**Descripción:**\n{nota.get('descripcion')}")
                    st.caption(f"ID: `{nota.get('id')}` | Última modificación: {nota.get('fecha_modificacion', 'N/A')}")
                    
                    col_opt1, col_opt2, _ = st.columns([1, 1, 4])
                    with col_opt1:
                        if st.button("✏️ Editar", key=f"edit_{nota['id']}"):
                            st.session_state["editando_nota_id"] = nota["id"]
                            st.rerun()
                    with col_opt2:
                        if st.button("🗑️ Eliminar", key=f"del_{nota['id']}"):
                            nuevas_notas = [n for n in notas_actuales if n["id"] != nota["id"]]
                            mensaje_commit = f"Eliminar nota: {nota.get('titulo')}"
                            _, sha_fresco = obtener_notas_github()
                            exito_del = guardar_notas_github(nuevas_notas, sha_fresco, mensaje_commit)
                            if exito_del:
                                st.success(f"Nota '{nota.get('titulo')}' eliminada correctamente.")
                                st.rerun()
