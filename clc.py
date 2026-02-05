import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Flor de Sauco App", layout="wide", initial_sidebar_state="collapsed")

# Estilo para celular
st.markdown("""
    <style>
    .stButton>button { width: 100%; height: 3.5em; border-radius: 12px; font-weight: bold; background-color: #f0f2f6; }
    [data-testid="stHeader"] { visibility: hidden; }
    .block-container { padding-top: 1rem; }
    </style>
    """, unsafe_allow_html=True)

DB_FILE = "inventario_flor_de_sauco.xlsx"
DEPOSITOS = ["Molino", "Despacho", "Fábrica"]

def cargar_datos():
    if os.path.exists(DB_FILE):
        try:
            df_cat = pd.read_excel(DB_FILE, sheet_name="Catalogo").copy()
            df_movs = pd.read_excel(DB_FILE, sheet_name="Movimientos").copy()
            return df_cat, df_movs
        except: return pd.DataFrame(), pd.DataFrame()
    return pd.DataFrame(), pd.DataFrame()

def guardar_datos(df_c, df_m):
    try:
        with pd.ExcelWriter(DB_FILE, engine="openpyxl") as writer:
            df_c.to_excel(writer, sheet_name="Catalogo", index=False)
            df_m.to_excel(writer, sheet_name="Movimientos", index=False)
        return True
    except:
        st.error("❌ El archivo está abierto en otro lado. Cerralo para guardar.")
        return False

df_cat, df_movs = cargar_datos()
menu = st.tabs(["📊 Stock", "🔄 Transferir", "📥 Carga", "⚙️ Ajustes"])

# --- 1. STOCK (CON BUSCADOR Y PROVEEDOR) ---
with menu[0]:
    st.subheader("📊 Stock Actual")
    busk = st.text_input("🔍 Buscar (Producto o Proveedor):")
    dep_s = st.selectbox("Sector:", DEPOSITOS)
    
    if not df_movs.empty:
        m_dep = df_movs[df_movs["Deposito"] == dep_s]
        ing = m_dep[m_dep["Tipo"] == "Ingreso"].groupby("Producto")["Cantidad"].sum()
        egr = m_dep[m_dep["Tipo"] == "Egreso"].groupby("Producto")["Cantidad"].sum()
        stk = ing.add(-egr, fill_value=0).reset_index()
        stk.columns = ["Producto", "Cantidad"]
        
        final = pd.merge(stk, df_cat, on="Producto", how="left")
        if busk:
            final = final[(final["Producto"].str.contains(busk, case=False, na=False)) | 
                          (final["Proveedor"].str.contains(busk, case=False, na=False))]
        
        st.dataframe(final[["Producto", "Cantidad", "Proveedor"]], use_container_width=True, hide_index=True)

# --- 2. CARGA (UNIDADES Y FARDOS REPARADO) ---
with menu[2]:
    st.subheader("📥 Registro Manual")
    if not df_cat.empty:
        p_sel = st.selectbox("Producto:", sorted(df_cat["Producto"].unique().tolist()))
        # Obtener unidades por fardo
        u_f = float(df_cat[df_cat["Producto"] == p_sel]["Unidades_Fardo"].values[0]) if "Unidades_Fardo" in df_cat.columns else 1.0
        
        modo = st.radio("Cargar por:", ["Unidades/Kg", "Fardos"], horizontal=True)
        c_in = st.number_input("Cantidad:", min_value=0.0)
        
        c_final = c_in * u_f if modo == "Fardos" else c_in
        if modo == "Fardos": st.info(f"Total: {c_final} unidades")

        tipo = st.radio("Operación:", ["Ingreso", "Egreso"], horizontal=True)
        dep = st.selectbox("Destino:", DEPOSITOS)
        
        if st.button("💾 Guardar"):
            f = datetime.now().strftime("%Y-%m-%d %H:%M")
            n = pd.DataFrame([[f, p_sel, tipo, c_final, dep]], columns=["Fecha", "Producto", "Tipo", "Cantidad", "Deposito"])
            if guardar_datos(df_cat, pd.concat([df_movs, n], ignore_index=True)):
                st.success("✅ Guardado"); st.rerun()

# --- 4. AJUSTES (LA PARTE QUE NECESITÁS) ---
with menu[3]:
    st.subheader("⚙️ Importación Masiva")
    st.write("Tu Excel debe tener las columnas: **Producto, Proveedor, Unidades_Fardo, Molino, Despacho, Fábrica**.")
    
    archivo = st.file_uploader("Subí tu Excel con stock inicial", type=["xlsx"])
    
    if archivo:
        if st.button("🚀 PROCESAR TODO EL EXCEL"):
            df_new = pd.read_excel(archivo)
            # 1. Crear el catálogo
            cat_cols = ["Producto", "Proveedor", "Unidades_Fardo"]
            df_cat_new = df_new[[c for c in cat_cols if c in df_new.columns]].copy()
            
            # 2. Convertir columnas de stock en movimientos
            lista_m = []
            f_now = datetime.now().strftime("%Y-%m-%d %H:%M")
            columnas_stock = {"Molino": "Molino", "Despacho": "Despacho", "Fábrica": "Fábrica"}
            
            for _, fila in df_new.iterrows():
                for col_excel, nombre_dep in columnas_stock.items():
                    if col_excel in df_new.columns:
                        valor = pd.to_numeric(fila[col_excel], errors='coerce')
                        if valor > 0:
                            lista_m.append([f_now, fila["Producto"], "Ingreso", valor, nombre_dep])
            
            df_movs_new = pd.DataFrame(lista_m, columns=["Fecha", "Producto", "Tipo", "Cantidad", "Deposito"])
            
            # Guardar ambos
            if guardar_datos(df_cat_new, df_movs_new):
                st.success("✅ ¡Todo cargado! Stock, proveedores y fardos actualizados.")
                st.balloons(); st.rerun()
