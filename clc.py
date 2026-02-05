import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- 1. CONFIGURACIÓN DE INTERFAZ APP ---
st.set_page_config(
    page_title="Flor de Sauco App", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# Estilo visual para que en el celular parezca una aplicación nativa
st.markdown("""
    <style>
    .stButton>button { width: 100%; height: 3.5em; border-radius: 12px; font-weight: bold; background-color: #f0f2f6; color: #333; }
    [data-testid="stHeader"] { visibility: hidden; }
    .block-container { padding-top: 1rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { 
        height: 50px; white-space: pre-wrap; background-color: #f9f9f9; 
        border-radius: 10px 10px 0 0; font-size: 14px;
    }
    </style>
    """, unsafe_allow_html=True)

DB_FILE = "inventario_flor_de_sauco.xlsx"
DEPOSITOS = ["Molino", "Despacho", "Fábrica"]

# --- 2. FUNCIONES DE DATOS ---
def cargar_datos():
    if os.path.exists(DB_FILE):
        try:
            df_c = pd.read_excel(DB_FILE, sheet_name="Catalogo").copy()
            df_m = pd.read_excel(DB_FILE, sheet_name="Movimientos").copy()
            # Aseguramos que las columnas necesarias existan
            if df_m.empty:
                df_m = pd.DataFrame(columns=["Fecha", "Producto", "Tipo", "Cantidad", "Deposito"])
            return df_c, df_m
        except: 
            return pd.DataFrame(columns=["Producto", "Proveedor", "Minimo", "Unidades_Fardo"]), \
                   pd.DataFrame(columns=["Fecha", "Producto", "Tipo", "Cantidad", "Deposito"])
    return pd.DataFrame(columns=["Producto", "Proveedor", "Minimo", "Unidades_Fardo"]), \
           pd.DataFrame(columns=["Fecha", "Producto", "Tipo", "Cantidad", "Deposito"])

def guardar_datos(df_c, df_m):
    try:
        with pd.ExcelWriter(DB_FILE, engine="openpyxl") as writer:
            df_c.to_excel(writer, sheet_name="Catalogo", index=False)
            df_m.to_excel(writer, sheet_name="Movimientos", index=False)
        return True
    except:
        st.error("❌ Archivo bloqueado. Si estás en la PC, cerrá el Excel.")
        return False

# Carga inicial de datos
df_cat, df_movs = cargar_datos()

# --- 3. MENÚ DE PESTAÑAS (Táctil) ---
menu = st.tabs(["📊 Stock", "🔄 Transferir", "📥 Carga", "⚙️ Ajustes"])

# --- PESTAÑA 1: STOCK Y BUSCADOR ---
with menu[0]:
    st.subheader("🔍 Consulta de Stock")
    busqueda = st.text_input("Buscar por nombre o proveedor:", key="busk_global")
    dep_sel = st.selectbox("Seleccionar Sector:", DEPOSITOS, key="sector_stk")
    
    if not df_movs.empty:
        # Filtrar movimientos del depósito seleccionado
        m_dep = df_movs[df_movs["Deposito"] == dep_sel]
        if not m_dep.empty:
            ing = m_dep[m_dep["Tipo"] == "Ingreso"].groupby("Producto")["Cantidad"].sum()
            egr = m_dep[m_dep["Tipo"] == "Egreso"].groupby("Producto")["Cantidad"].sum()
            stk_final = ing.add(-egr, fill_value=0).reset_index()
            stk_final.columns = ["Producto", "Disponible"]
            
            # Unimos con el catálogo para traer Proveedor y Mínimo
            resultado = pd.merge(stk_final, df_cat, on="Producto", how="left")
            
            # Filtro por buscador
            if busqueda:
                mask = resultado["Producto"].str.contains(busqueda, case=False, na=False) | \
                       resultado["Proveedor"].str.contains(busqueda, case=False, na=False)
                resultado = resultado[mask]
            
            st.dataframe(resultado[["Producto", "Disponible", "Proveedor", "Minimo"]], 
                         use_container_width=True, hide_index=True)
        else:
            st.info(f"No hay movimientos en {dep_sel}")
    else:
        st.warning("No hay datos de movimientos registrados.")

# --- PESTAÑA 2: TRANSFERENCIAS CON BLOQUEO ---
with menu[1]:
    st.subheader("🔄 Mover entre Sectores")
    if not df_cat.empty:
        prod_t = st.selectbox("Producto:", sorted(df_cat["Producto"].astype(str).tolist()), key="p_t")
        col1, col2 = st.columns(2)
        with col1: orig_t = st.selectbox("Desde:", DEPOSITOS, key="o_t")
        with col2: dest_t = st.selectbox("Hacia:", [d for d in DEPOSITOS if d != orig_t], key="d_t")
        cant_t = st.number_input("Cantidad:", min_value=0.0, step=1.0, key="c_t")
        
        # Calcular stock disponible en el origen
        stk_origen = 0
        if not df_movs.empty:
            df_f = df_movs[(df_movs["Producto"] == prod_t) & (df_movs["Deposito"] == orig_t)]
            stk_origen = df_f[df_f["Tipo"]=="Ingreso"]["Cantidad"].sum() - df_f[df_f["Tipo"]=="Egreso"]["Cantidad"].sum()

        forzar_t = st.toggle("⚠️ Forzar transferencia (sin stock)")
        
        if st.button("🚀 Ejecutar Transferencia"):
            if stk_origen < cant_t and not forzar_t:
                st.error(f"Bloqueado: Solo hay {stk_origen} en {orig_t}")
            elif cant_t <= 0:
                st.warning("La cantidad debe ser mayor a 0")
            else:
                f_now = datetime.now().strftime("%Y-%m-%d %H:%M")
                egr = pd.DataFrame([[f_now, prod_t, "Egreso", cant_t, orig_t]], columns=df_movs.columns)
                ing = pd.DataFrame([[f_now, prod_t, "Ingreso", cant_t, dest_t]], columns=df_movs.columns)
                if guardar_datos(df_cat, pd.concat([df_movs, egr, ing], ignore_index=True)):
                    st.success("¡Movimiento registrado!")
                    st.rerun()

# --- PESTAÑA 3: CARGA (UNIDADES O FARDOS) ---
with menu[2]:
    st.subheader("📥 Carga de Mercadería")
    if not df_cat.empty:
        prod_c = st.selectbox("Producto:", sorted(df_cat["Producto"].astype(str).tolist()), key="p_c")
        
        # Buscamos cuánto trae el fardo de este producto
        info_prod = df_cat[df_cat["Producto"] == prod_c]
        u_fardo = float(info_prod["Unidades_Fardo"].values[0]) if not info_prod.empty else 1.0
        
        modo_c = st.radio("Cargar por:", ["Unidades / Kg", "Fardos"], horizontal=True)
        valor_c = st.number_input(f"Cantidad de {modo_c}:", min_value=0.0, step=1.0)
        
        # Cálculo final
        cant_final_c = valor_c * u_fardo if modo_c == "Fardos" else valor_c
        
        if modo_c == "Fardos":
            st.info(f"Equivale a: {cant_final_c} unidades.")

        tipo_c = st.radio("Tipo:", ["Ingreso", "Egreso"], horizontal=True, key="t_c")
        dep_c = st.selectbox("Sector destino:", DEPOSITOS, key="d_c")
        
        if st.button("💾 Guardar en Inventario"):
            if cant_final_c > 0:
                f_now = datetime.now().strftime("%Y-%m-%d %H:%M")
                nuevo_mov = pd.DataFrame([[f_now, prod_c, tipo_c, cant_final_c, dep_c]], columns=df_movs.columns)
                if guardar_datos(df_cat, pd.concat([df_movs, nuevo_mov], ignore_index=True)):
                    st.success(f"Registrado: {cant_final_c} unidades.")
                    st.rerun()
            else:
                st.warning("Ingresá una cantidad válida.")

# --- PESTAÑA 4: AJUSTES (IMPORTACIÓN ACUMULATIVA) ---
with menu[3]:
    st.subheader("⚙️ Actualización de Catálogo")
    st.write("Subí tu Excel para actualizar productos sin borrar tus transferencias.")
    excel_subida = st.file_uploader("Elegir archivo Excel", type=["xlsx"])
    if excel_subida:
        if st.button("🚀 Actualizar Lista de Productos"):
            nuevo_cat = pd.read_excel(excel_subida)
            # Guardamos el nuevo catálogo pero mantenemos los movimientos intactos
            if guardar_datos(nuevo_cat, df_movs):
                st.success("Catálogo actualizado. Los movimientos se mantuvieron.")
                st.rerun()
