import json
import pandas as pd
from groq import Groq
import streamlit as st
from config.supabase_config import supabase_config

# Inicializar clientes
supabase = supabase_config()
groq_client = Groq(api_key=st.secrets["groq"]["API_KEY"], max_retries=2)

st.set_page_config(
    page_title="Registro por Voz - Finanzas", page_icon="🎙️", layout="centered"
)



# Inicializar estados de navegación y datos
if "seccion_actual" not in st.session_state:
    st.session_state.seccion_actual = "Inicio"

if "resultado_activo" not in st.session_state:
    st.session_state.resultado_activo = None

if "audio_key" not in st.session_state:
    st.session_state.audio_key = 0

# ==========================================
# VISTA: INICIO (Menú Principal)
# ==========================================
if st.session_state.seccion_actual == "Inicio":
    # Estilos CSS personalizados para compactar el componente de audio
    st.markdown("""
        <style>
            /* Reducir y centrar el contenedor del grabador de audio */
            div[data-testid="stAudioInput"] {
                display: flex;
                justify-content: center;
                align-items: center;
                margin: 0 auto;
                max-width: 300px;
            }
            div[data-testid="stAudioInput"] button {
                border-radius: 50% !important;
                width: 60px !important;
                height: 60px !important;
                background-color: #ff4b4b !important;
                color: white !important;
            }
        </style>
    """, unsafe_allow_html=True)

    st.title("🎙️ Registro Financiero por Voz")
    st.markdown("<p style='text-align: center;'>Toca el micrófono para registrar o consultar tus finanzas.</p>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Micrófono compacto
    audio_file = st.audio_input("Graba tu transacción:", key=f"audio_{st.session_state.audio_key}")

    if audio_file is not None:
        with st.spinner("🎧 Procesando audio con Whisper..."):
            audio_bytes = audio_file.read()
            audio_filename = "temp_audio.wav"

            with open(audio_filename, "wb") as f:
                f.write(audio_bytes)

            with open(audio_filename, "rb") as file:
                transcription = groq_client.audio.transcriptions.create(
                    file=(audio_filename, file.read()),
                    model="whisper-large-v3-turbo",
                    language="es",
                    response_format="text",
                )

        st.success(f"**Texto reconocido:** \"{transcription}\"")

        with st.spinner("🤖 Analizando transacción con Llama..."):
            prompt_sistema = """
            Eres un asistente financiero y de inventarios inteligente. Tu tarea es analizar la intención del usuario y responder en un JSON estricto. Si el usuario realiza varias solicitudes en el mismo audio, devuelve una lista de objetos JSON `[...]`. Cualquier otra intención será rechazada.

            REGLA CRÍTICA: En las acciones "REGISTRAR", "MODIFICAR" y "ELIMINAR", el usuario DEBE mencionar explícitamente la tabla. Si no la menciona, asigna "tabla": null.

            Identifica la intención:

            1. Si el usuario quiere REGISTRAR una nueva transacción:
                - Si la tabla es "ventas" o "compras":
                    {
                        "accion": "REGISTRAR",
                        "tabla": "ventas" | "compras",
                        "nombre": "nombre del producto",
                        "cantidad": número entero,
                        "precio": número o valor decimal,
                        "forma de pago": "efectivo" | "nequi" | "crédito" | "transferencia" | "tarjeta",
                        "fecha": "YYYY-MM-DD HH:mm:ss+ZZ" | null
                    }
                
                - Si la tabla es "gastos":
                    {
                        "accion": "REGISTRAR",
                        "tabla": "gastos",
                        "descripcion": "detalle del gasto",
                        "precio": número o valor decimal,
                        "forma de pago": "efectivo" | "nequi" | "crédito" | "transferencia" | "tarjeta",
                        "fecha": "YYYY-MM-DD HH:mm:ss+ZZ" | null
                    }

                - Si la tabla es "productos" (Inventario manual o inicial sin factura):
                    {
                        "accion": "REGISTRAR",
                        "tabla": "productos",
                        "nombre": "nombre del producto",
                        "stock_actual": número entero,
                        "stock_minimo": número entero,
                        "precio_venta": número o valor decimal,
                        "fecha_vencimiento": "YYYY-MM-DD" | null
                    }
                
                - Si la tabla es "abonos":
                 {
                    "accion": "REGISTRAR",
                    "tabla": "abonos",
                    "nombre": "nombre del cliente",
                    "apellido": "nombre del cliente",
                    "documento": "documento de identidad del cliente en texto",
                    "monto": número o valor decimal,
                    "forma de pago": "efectivo" | "nequi" | "crédito" | "transferencia" | "tarjeta",
                    "fecha": "YYYY-MM-DD HH:mm:ss+ZZ" | null,
                    "descripcion": "detalle del abono o null"
                 }
                 
                - Si la tabla es "pagos_proveedores":
                 {
                    "accion": "REGISTRAR",
                    "tabla": "pagos_proveedores",
                    "nombre": "nombre de la persona o contacto",
                    "empresa": "nombre de la compañía o proveedor o null",
                    "documento": "cédula o NIT del proveedor en texto",
                    "monto": número o valor decimal,
                    "forma de pago": "efectivo" | "nequi" | "crédito" | "transferencia" | "tarjeta",
                    "fecha": "YYYY-MM-DD HH:mm:ss+ZZ" | null,
                    "descripcion": "detalle o número de factura o null"
                 }

            2. Si el usuario quiere CONSULTAR información:
               {
                  "accion": "CONSULTAR",
                  "tabla": "ventas" | "compras" | "gastos" | "costos" | "abonos" | "pagos_proveedores" | "productos",
                  "metrica": "total" | "conteo",
                  "filtro_metodo": "efectivo" | "nequi" | "crédito" | "transferencia" | "tarjeta" | null,
                  "periodo": "diario" | "semanal" | "mensual" | null,
                  "mes": número entero (1-12) o null,
                  "anio": número entero (ej: 2025, 2026) o null
               }
            
            3. Si el usuario quiere MODIFICAR, ACTUALIZAR o COMPLETAR un dato existente:
               - Si la tabla es "ventas" o "compras" o "productos":
                {
                    "accion": "MODIFICAR",
                    "tabla": "ventas" | "compras" | "productos",
                    "criterio_busqueda": {
                        "nombre": "nombre del producto o null",
                        "id": "uuid del registro o null"
                    },
                    "datos_a_actualizar": {
                        "nombre": "nuevo nombre del producto o null",
                        "cantidad": número entero o null,
                        "stock_actual": número entero o null,
                        "stock_minimo": número entero o null,
                        "precio": número o valor decimal o null,
                        "precio_venta": número o valor decimal o null,
                        "forma de pago": "efectivo" | "nequi" | "crédito" | "transferencia" | "tarjeta" | null,
                        "fecha_vencimiento": "YYYY-MM-DD" | null,
                        "fecha": "YYYY-MM-DD HH:mm:ss+ZZ" | null
                    }
                }

                - Si la tabla es "gastos":
                {
                    "accion": "MODIFICAR",
                    "tabla": "gastos",
                    "criterio_busqueda": {
                        "descripcion": "detalle del gasto",
                        "fecha": "YYYY-MM-DD HH:mm:ss+ZZ o null"
                    },
                    "datos_a_actualizar": {
                        "descripcion": "nueva descripción del gasto o null",
                        "precio": número o valor decimal o null,
                        "forma de pago": "efectivo" | "nequi" | "crédito" | "transferencia" | "tarjeta" | null,
                        "fecha": "YYYY-MM-DD HH:mm:ss+ZZ" | null
                    }
                }

                - Si la tabla es "abonos":
                {
                    "accion": "MODIFICAR",
                    "tabla": "abonos",
                    "criterio_busqueda": {
                        "documento": "documento de identidad del cliente o null",
                        "id": "uuid del abono o null"
                    },
                    "datos_a_actualizar": {
                        "nombre": "nuevo nombre del cliente o null",
                        "apellido": "nuevo apellido del cliente o null",
                        "documento": "nuevo documento de identidad o null",
                        "monto": número o valor decimal o null,
                        "forma de pago": "efectivo" | "nequi" | "crédito" | "transferencia" | "tarjeta" | null,
                        "fecha": "YYYY-MM-DD HH:mm:ss+ZZ" | null,
                        "descripcion": "nuevo detalle del abono o null"
                    }
                }

                - Si la tabla es "pagos_proveedores":
                {
                    "accion": "MODIFICAR",
                    "tabla": "pagos_proveedores",
                    "criterio_busqueda": {
                        "documento": "cédula o NIT del proveedor o null",
                        "id": "uuid del pago o null"
                    },
                    "datos_a_actualizar": {
                        "nombre": "nuevo nombre de la persona o contacto o null",
                        "empresa": "nuevo nombre de la compañía o proveedor o null",
                        "documento": "nueva cédula o NIT o null",
                        "monto": número o valor decimal o null,
                        "forma de pago": "efectivo" | "nequi" | "crédito" | "transferencia" | "tarjeta" | null,
                        "fecha": "YYYY-MM-DD HH:mm:ss+ZZ" | null,
                        "descripcion": "nuevo detalle o número de factura o null"
                    }
                }

            4. Si el usuario quiere ELIMINAR o BORRAR un registro existente:
               {
                  "accion": "ELIMINAR",
                  "tabla": "ventas" | "abonos" | "gastos" | "compras" | "pagos_proveedores" | "productos",
                  "criterio_busqueda": {
                      "nombre": "nombre del producto o null"
                      "codigo": numero de codigo
                  }
               }

            No devuelvas texto adicional, solo el JSON estructurado (objeto o lista).
            """

            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": transcription},
                ],
                model="openai/gpt-oss-120b",
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            contenido_crudo = chat_completion.choices[0].message.content
            resultado_cargado = json.loads(contenido_crudo)

            if isinstance(resultado_cargado, dict) and "acciones" in resultado_cargado:
                resultado_json = resultado_cargado["acciones"]
            else:
                resultado_json = resultado_cargado

        st.session_state.resultado_activo = resultado_json
        st.session_state.audio_key += 1
        st.rerun()

    # Procesar y mostrar acciones pendientes si las hay en el Home
    if st.session_state.resultado_activo:
        resultados = st.session_state.resultado_activo
        if not isinstance(resultados, list):
            resultados = [resultados]

        for i, resultado_json in enumerate(resultados):
            st.markdown(f"--- \n### 🔄 Acción {i + 1}")
            st.json(resultado_json)

        tiene_escrituras = any(r.get("accion") in ["REGISTRAR", "MODIFICAR", "ELIMINAR"] for r in resultados)
        if tiene_escrituras:
            if st.button("🚀 Ejecutar Acción(es)", type="primary"):
                for i, resultado_json in enumerate(resultados):
                    accion = resultado_json.get("accion")
                    tabla = resultado_json.get("tabla")
                    if not tabla:
                        continue

                    # Función interna para normalizar el nombre del producto de forma inteligente
                    def normalizar_nombre_producto(nombre_crudo):
                        if not nombre_crudo:
                            return nombre_crudo
                        n = str(nombre_crudo).lower()
                        if "volcán" in n or "volcan" in n:
                            return "Café Volcán en granos 250gr"
                        elif "finca" in n:
                            return "Café Finca en grano 454gr"
                        elif "mujeres" in n or "cafeteras" in n:
                            return "Café Mujeres Cafeteras en granos 454gr"
                        elif "nariño" in n or "narino" in n:
                            return "Café Origen Nariño en granos 454gr"
                        elif "colina" in n:
                            return "Café Colina en grano 454gr"
                        return nombre_crudo

                    if accion == "REGISTRAR":
                        try:
                            datos_insertar = {
                                k.upper(): v for k, v in resultado_json.items() 
                                if k.upper() not in ["ACCION", "TABLA"] and v is not None
                            }
                            
                            # Validación obligatoria de la forma de pago para tablas que lo requieren
                            if tabla in ["ventas", "compras", "gastos", "abonos", "pagos_proveedores"]:
                                forma_pago = datos_insertar.get("FORMA DE PAGO")
                                if not forma_pago or str(forma_pago).lower() == "null" or str(forma_pago).strip() == "":
                                    st.warning(f"⚠️ Acción {i+1}: ¡Es obligatorio indicar la forma de pago (efectivo, nequi, transferencia, etc.)!")
                                    continue

                            # Normalizar el nombre PRIMERO para que coincida con el catálogo oficial
                            if tabla in ["compras", "ventas", "productos"] and "NOMBRE" in datos_insertar:
                                datos_insertar["NOMBRE"] = normalizar_nombre_producto(datos_insertar["NOMBRE"])

                            nombre_prod = datos_insertar.get("NOMBRE")
                            
                            # Si no se dictó el precio, buscar usando el nombre ya normalizado
                            if nombre_prod and (tabla in ["ventas", "compras"]) and ("PRECIO" not in datos_insertar or not datos_insertar["PRECIO"] or datos_insertar["PRECIO"] == 0):
                                precio_encontrado = 0
                                
                                res_prod_precio = supabase.table("productos").select("*").ilike("NOMBRE", nombre_prod).execute()
                                if res_prod_precio.data and len(res_prod_precio.data) > 0:
                                    prod_info = res_prod_precio.data[0]
                                    criterio_busqueda_precio = ["PRECIO VENTA", "PRECIO", "PRECIO DE VENTA"]
                                    key_precio = next((k for k in prod_info.keys() if k.upper() in criterio_busqueda_precio), None)
                                    if key_precio and prod_info[key_precio]:
                                        precio_encontrado = prod_info[key_precio]
                                
                                if not precio_encontrado or precio_encontrado == 0:
                                    res_historial = supabase.table(tabla).select("PRECIO").ilike("NOMBRE", nombre_prod).limit(1).execute()
                                    if res_historial.data and len(res_historial.data) > 0:
                                        precio_encontrado = res_historial.data[0].get("PRECIO", 0)

                                if precio_encontrado and precio_encontrado > 0:
                                    datos_insertar["PRECIO"] = precio_encontrado
                                else:
                                    st.warning(f"⚠️ Acción {i+1}: No se encontró un precio registrado para '{nombre_prod}'. Se asignará 0.")
                                    datos_insertar["PRECIO"] = 0

                            # Guardar la transacción original en su tabla correspondiente
                            supabase.table(tabla).insert(datos_insertar).execute()
                            st.success(f"¡Registro {i+1} guardado con éxito en '{tabla}'!")

                            # -------------------------------------------------------------
                            # INTEGRACIÓN AUTOMÁTICA CON EL MÓDULO DE INVENTARIOS (PRODUCTOS)
                            # -------------------------------------------------------------
                            cantidad_movida = int(datos_insertar.get("CANTIDAD", 0))

                            if nombre_prod and cantidad_movida > 0:
                                res_prod = supabase.table("productos").select("*").ilike("NOMBRE", nombre_prod).execute()
                                
                                if tabla == "compras":
                                    if res_prod.data and len(res_prod.data) > 0:
                                        prod_existente = res_prod.data[0]
                                        key_stock = "STOCK ACTUAL"
                                        stock_actual = int(prod_existente.get(key_stock, 0))
                                        nuevo_stock = stock_actual + cantidad_movida

                                        codigo_val = prod_existente.get("CODIGO")
                                        supabase.table("productos").update({key_stock: nuevo_stock}).eq("CODIGO", codigo_val).execute()
                                    else:
                                        fecha_venc = datos_insertar.get("FECHA_VENCIMIENTO") or datos_insertar.get("FECHA VENCIMIENTO")
                                        nuevo_prod = {
                                            "NOMBRE": nombre_prod,
                                            "STOCK ACTUAL": cantidad_movida,
                                            "STOCK MINIMO": 5,
                                            "PRECIO VENTA": datos_insertar.get("PRECIO", 0)
                                        }
                                        if fecha_venc:
                                            nuevo_prod["FECHA VENCIMIENTO"] = fecha_venc
                                        supabase.table("productos").insert(nuevo_prod).execute()

                                elif tabla == "ventas":
                                    if res_prod.data and len(res_prod.data) > 0:
                                        prod_existente = res_prod.data[0]
                                        key_stock = "STOCK ACTUAL"
                                        stock_actual = int(prod_existente.get(key_stock, 0))
                                        nuevo_stock = max(0, stock_actual - cantidad_movida)

                                        codigo_val = prod_existente.get("CODIGO")
                                        supabase.table("productos").update({key_stock: nuevo_stock}).eq("CODIGO", codigo_val).execute()

                        except Exception as e:
                            st.error(f"Error al guardar registro {i+1}: {e}")

                    elif accion == "MODIFICAR":
                        try:
                            criterio = {
                                k.upper(): v for k, v in resultado_json.get("criterio_busqueda", {}).items() 
                                if v is not None and v != ""
                            }
                            nuevos_datos = {
                                k.upper(): v for k, v in resultado_json.get("datos_a_actualizar", {}).items() 
                                if v is not None and v != ""
                            }
                            
                            if tabla in ["compras", "ventas", "productos"] and "NOMBRE" in nuevos_datos:
                                nuevos_datos["NOMBRE"] = normalizar_nombre_producto(nuevos_datos["NOMBRE"])

                            tiene_id = "ID" in criterio or "CODIGO" in criterio
                            tiene_tiempo = any(k in criterio for k in ["FECHA", "TIEMPO", "HORA"])
                            tiene_nombre = "NOMBRE" in criterio or "DESCRIPCION" in criterio
                            
                            if not (tiene_id or tiene_tiempo or tiene_nombre):
                                st.warning(f"⚠️ Acción {i+1}: Debes proporcionar un criterio para identificar el registro.")
                                continue

                            query = supabase.table(tabla).update(nuevos_datos)
                            for k, v in criterio.items():
                                if isinstance(v, str):
                                    query = query.ilike(k, f"%{v}%")
                                else:
                                    query = query.eq(k, v)
                            
                            response = query.execute()
                            if response.data:
                                st.success(f"¡Registro {i+1} actualizado correctamente!")
                            else:
                                st.warning(f"No se encontró coincidencia para la acción {i+1}.")
                        except Exception as e:
                            st.error(f"Error al actualizar acción {i+1}: {e}")

                    elif accion == "ELIMINAR":
                        try:
                            criterio = {
                                k.upper(): v for k, v in resultado_json.get("criterio_busqueda", {}).items() 
                                if v is not None and v != ""
                            }
                            
                            query = supabase.table(tabla).delete()
                            for k, v in criterio.items():
                                if isinstance(v, str):
                                    query = query.ilike(k, f"%{v}%")
                                else:
                                    query = query.eq(k, v)
                            
                            response = query.execute()
                            if response.data:
                                st.success(f"¡Registro {i+1} eliminado correctamente de '{tabla}'!")
                            else:
                                st.warning(f"No se encontró coincidencia para eliminar en la acción {i+1}.")
                        except Exception as e:
                            st.error(f"Error al eliminar registro {i+1}: {e}")

    st.markdown("---")
    st.markdown("### Menú Principal")

    # Estilos CSS modernos para transformar los botones en tarjetas táctiles estilo app móvil cafetera
    st.markdown("""
        <style>
            /* Contenedor general para dar espacio y evitar toques accidentales */
            .stButton {
                margin-bottom: 12px;
            }
            /* Estilo personalizado para los botones grandes de navegación */
            div.stButton > button {
                width: 100% !important;
                height: 95px !important;
                background: linear-gradient(135deg, #4A3319 0%, #6F4E37 100%) !important;
                color: #FFF8E8 !important;
                border: 2px solid #8D5524 !important;
                border-radius: 16px !important;
                font-size: 18px !important;
                font-weight: 600 !important;
                box-shadow: 0 4px 12px rgba(74, 51, 25, 0.25) !important;
                transition: all 0.3s ease !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: center !important;
                align-items: center !important;
            }
            div.stButton > button:hover {
                background: linear-gradient(135deg, #6F4E37 0%, #8D5524 100%) !important;
                border-color: #D2B48C !important;
                box-shadow: 0 6px 16px rgba(111, 78, 55, 0.4) !important;
                transform: translateY(-2px);
            }
            div.stButton > button:active {
                transform: translateY(1px);
            }
        </style>
    """, unsafe_allow_html=True)
    
    # 5 botones grandes distribuidos en columnas para una experiencia táctil móvil óptima
    col_b1, col_b2, col_b3, col_b4, col_b5 = st.columns(5)
    
    with col_b1:
        if st.button("💰\nIngresos", use_container_width=True):
            st.session_state.seccion_actual = "Ingresos"
            st.rerun()
    with col_b2:
        if st.button("🛒\nCompras", use_container_width=True):
            st.session_state.seccion_actual = "Compras"
            st.rerun()
    with col_b3:
        if st.button("💸\nGastos", use_container_width=True):
            st.session_state.seccion_actual = "Gastos"
            st.rerun()
    with col_b4:
        if st.button("☕\nInventario", use_container_width=True):
            st.session_state.seccion_actual = "Control de Inventario"
            st.rerun()
    with col_b5:
        if st.button("📊\nReportes", use_container_width=True):
            st.session_state.seccion_actual = "Reportes"
            st.rerun()

# ==========================================
# VISTAS DE LAS SECCIONES ESPECÍFICAS
# ==========================================
else:
    if st.button("⬅️ Regresar al Menú Principal"):
        st.session_state.seccion_actual = "Inicio"
        st.session_state.resultado_activo = None
        st.rerun()

    seccion = st.session_state.seccion_actual

    if seccion == "Ingresos":
        st.title("💰 Sección: Ingresos")
        st.markdown("Los ingresos son todas las entradas de dinero o recursos económicos que recibe una persona o empresa como resultado de su actividad.")
        st.markdown("---")

        sub_opcion = st.radio(
            "Selecciona qué deseas consultar o registrar:",
            ["Registro diario de ventas", "Registro de abonos de clientes", "Reporte de ingresos (Diario, Semanal, Mensual)"],
            horizontal=True
        )

        if sub_opcion == "Registro diario de ventas":
            st.subheader("📋 Registro Diario de Ventas")
            try:
                res = supabase.table("ventas").select("*").range(0, 9999).execute()
                df = pd.DataFrame(res.data)
                if not df.empty:
                    df.columns = df.columns.str.lower()
                    if "fecha" in df.columns:
                        df["fecha_dt"] = pd.to_datetime(df["fecha"], errors="coerce").dt.tz_localize(None)
                        hoy = pd.Timestamp.now().date()
                        df = df[df["fecha_dt"].dt.date == hoy]
                        df = df.drop(columns=["fecha_dt"])

                    if not df.empty:
                        if "cantidad" in df.columns and "precio" in df.columns:
                            df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0)
                            df["precio"] = pd.to_numeric(df["precio"], errors="coerce").fillna(0)
                            df["subtotal"] = df["cantidad"] * df["precio"]
                            
                            df["precio"] = df["precio"].apply(lambda x: f"${x:,.2f}")
                            df["subtotal"] = df["subtotal"].apply(lambda x: f"${x:,.2f}")

                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("No hay ventas registradas para el día de hoy.")
                else:
                    st.info("No hay registros en la tabla de ventas.")
            except Exception as e:
                st.error(f"Error al cargar ventas: {e}")

        elif sub_opcion == "Registro de abonos de clientes":
            st.subheader("💳 Registro de Abonos de Clientes")
            try:
                res = supabase.table("abonos").select("*").range(0, 9999).execute()
                df = pd.DataFrame(res.data)
                if not df.empty:
                    df.columns = df.columns.str.lower()
                    if "monto" in df.columns:
                        df["monto"] = pd.to_numeric(df["monto"], errors="coerce").fillna(0)
                        df["monto"] = df["monto"].apply(lambda x: f"${x:,.2f}")
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No hay abonos registrados.")
            except Exception as e:
                st.error(f"Error al cargar abonos: {e}")

        elif sub_opcion == "Reporte de ingresos (Diario, Semanal, Mensual)":
            st.subheader("📊 Reporte de Ingresos")
            tipo_reporte = st.selectbox("Selecciona el periodo del reporte:", ["Diario", "Semanal", "Mensual"])
            
            try:
                res = supabase.table("ventas").select("*").range(0, 9999).execute()
                df = pd.DataFrame(res.data)
                if not df.empty:
                    df.columns = df.columns.str.lower()
                    if "fecha" in df.columns:
                        df["fecha_dt"] = pd.to_datetime(df["fecha"], errors="coerce").dt.tz_localize(None)
                        ahora = pd.Timestamp.now()

                        if tipo_reporte == "Diario":
                            target_fecha = ahora.date()
                            df = df[df["fecha_dt"].dt.date == target_fecha]
                        elif tipo_reporte == "Semanal":
                            inicio_semana = (ahora - pd.Timedelta(days=ahora.dayofweek)).normalize()
                            fin_semana = inicio_semana + pd.Timedelta(days=6, hours=23, minutes=59, seconds=59)
                            df = df[(df["fecha_dt"] >= inicio_semana) & (df["fecha_dt"] <= fin_semana)]
                        elif tipo_reporte == "Mensual":
                            df = df[(df["fecha_dt"].dt.year == ahora.year) & (df["fecha_dt"].dt.month == ahora.month)]

                        df = df.drop(columns=["fecha_dt"])

                    if not df.empty:
                        if "cantidad" in df.columns and "precio" in df.columns:
                            df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0)
                            df["precio"] = pd.to_numeric(df["precio"], errors="coerce").fillna(0)
                            total_ingresos = (df["cantidad"] * df["precio"]).sum()
                            
                            df["subtotal"] = df["cantidad"] * df["precio"]
                            df["precio"] = df["precio"].apply(lambda x: f"${x:,.2f}")
                            df["subtotal"] = df["subtotal"].apply(lambda x: f"${x:,.2f}")
                        elif "monto" in df.columns:
                            df["monto"] = pd.to_numeric(df["monto"], errors="coerce").fillna(0)
                            total_ingresos = df["monto"].sum()
                            df["monto"] = df["monto"].apply(lambda x: f"${x:,.2f}")
                        else:
                            total_ingresos = 0

                        st.metric(label=f"Total Ingresos ({tipo_reporte})", value=f"${total_ingresos:,.2f}")
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info(f"No hay registros de ingresos para el reporte {tipo_reporte.lower()}.")
                else:
                    st.info("No hay datos disponibles en ventas.")
            except Exception as e:
                st.error(f"Error al generar reporte: {e}")

    elif seccion == "Compras":
        st.title("🛒 Sección: Compras")
        st.markdown("Las compras son todas las adquisiciones de bienes o servicios realizadas para la actividad del negocio.")
        st.markdown("---")

        sub_opcion = st.radio(
            "Selecciona qué deseas consultar o registrar:",
            ["Registro diario de compras", "Registro de pagos a proveedores", "Reporte de compras (Diario, Semanal, Mensual)"],
            horizontal=True
        )

        if sub_opcion == "Registro diario de compras":
            st.subheader("📋 Registro Diario de Compras")
            try:
                res = supabase.table("compras").select("*").range(0, 9999).execute()
                df = pd.DataFrame(res.data)
                if not df.empty:
                    df.columns = df.columns.str.lower()
                    if "fecha" in df.columns:
                        df["fecha_dt"] = pd.to_datetime(df["fecha"], errors="coerce").dt.tz_localize(None)
                        hoy = pd.Timestamp.now().date()
                        df = df[df["fecha_dt"].dt.date == hoy]
                        df = df.drop(columns=["fecha_dt"])

                    if not df.empty:
                        if "cantidad" in df.columns and "precio" in df.columns:
                            df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0)
                            df["precio"] = pd.to_numeric(df["precio"], errors="coerce").fillna(0)
                            df["subtotal"] = df["cantidad"] * df["precio"]
                            
                            df["precio"] = df["precio"].apply(lambda x: f"${x:,.2f}")
                            df["subtotal"] = df["subtotal"].apply(lambda x: f"${x:,.2f}")

                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("No hay compras registradas para el día de hoy.")
                else:
                    st.info("No hay registros en la tabla de compras.")
            except Exception as e:
                st.error(f"Error al cargar compras: {e}")

        elif sub_opcion == "Registro de pagos a proveedores":
            st.subheader("💳 Registro de Pagos a Proveedores")
            try:
                res = supabase.table("pagos_proveedores").select("*").range(0, 9999).execute()
                df = pd.DataFrame(res.data)
                if not df.empty:
                    df.columns = df.columns.str.lower()
                    if "monto" in df.columns:
                        df["monto"] = pd.to_numeric(df["monto"], errors="coerce").fillna(0)
                        df["monto"] = df["monto"].apply(lambda x: f"${x:,.2f}")
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No hay pagos a proveedores registrados.")
            except Exception as e:
                st.error(f"Error al cargar pagos a proveedores: {e}")

        elif sub_opcion == "Reporte de compras (Diario, Semanal, Mensual)":
            st.subheader("📊 Reporte de Compras")
            tipo_reporte = st.selectbox("Selecciona el periodo del reporte:", ["Diario", "Semanal", "Mensual"], key="reporte_compras_select")
            
            try:
                res = supabase.table("compras").select("*").range(0, 9999).execute()
                df = pd.DataFrame(res.data)
                if not df.empty:
                    df.columns = df.columns.str.lower()
                    if "fecha" in df.columns:
                        df["fecha_dt"] = pd.to_datetime(df["fecha"], errors="coerce").dt.tz_localize(None)
                        ahora = pd.Timestamp.now()

                        if tipo_reporte == "Diario":
                            target_fecha = ahora.date()
                            df = df[df["fecha_dt"].dt.date == target_fecha]
                        elif tipo_reporte == "Semanal":
                            inicio_semana = (ahora - pd.Timedelta(days=ahora.dayofweek)).normalize()
                            fin_semana = inicio_semana + pd.Timedelta(days=6, hours=23, minutes=59, seconds=59)
                            df = df[(df["fecha_dt"] >= inicio_semana) & (df["fecha_dt"] <= fin_semana)]
                        elif tipo_reporte == "Mensual":
                            df = df[(df["fecha_dt"].dt.year == ahora.year) & (df["fecha_dt"].dt.month == ahora.month)]

                        df = df.drop(columns=["fecha_dt"])

                    if not df.empty:
                        if "cantidad" in df.columns and "precio" in df.columns:
                            df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0)
                            df["precio"] = pd.to_numeric(df["precio"], errors="coerce").fillna(0)
                            total_compras = (df["cantidad"] * df["precio"]).sum()
                            
                            df["subtotal"] = df["cantidad"] * df["precio"]
                            df["precio"] = df["precio"].apply(lambda x: f"${x:,.2f}")
                            df["subtotal"] = df["subtotal"].apply(lambda x: f"${x:,.2f}")
                        elif "monto" in df.columns:
                            df["monto"] = pd.to_numeric(df["monto"], errors="coerce").fillna(0)
                            total_compras = df["monto"].sum()
                            df["monto"] = df["monto"].apply(lambda x: f"${x:,.2f}")
                        else:
                            total_compras = 0

                        st.metric(label=f"Total Compras ({tipo_reporte})", value=f"${total_compras:,.2f}")
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info(f"No hay registros de compras para el reporte {tipo_reporte.lower()}.")
                else:
                    st.info("No hay datos disponibles en compras.")
            except Exception as e:
                st.error(f"Error al generar reporte: {e}")

    elif seccion == "Gastos":
        st.title("💸 Sección: Gastos")
        st.markdown("Un gasto es un desembolso de dinero que hace un negocio para poder funcionar, pero que no se convierte en inventario ni en un activo para vender.")
        st.markdown("---")

        sub_opcion = st.radio(
            "Selecciona qué deseas consultar o registrar:",
            ["Registro diario de gastos", "Registro de pagos de gastos", "Reporte de gastos (Diario, Semanal, Mensual)"],
            horizontal=True,
            key="radio_gastos"
        )

        if sub_opcion == "Registro diario de gastos":
            st.subheader("📋 Registro Diario de Gastos")
            try:
                res = supabase.table("gastos").select("*").range(0, 9999).execute()
                df = pd.DataFrame(res.data)
                if not df.empty:
                    df.columns = df.columns.str.lower()
                    if "fecha" in df.columns:
                        df["fecha_dt"] = pd.to_datetime(df["fecha"], errors="coerce").dt.tz_localize(None)
                        hoy = pd.Timestamp.now().date()
                        df = df[df["fecha_dt"].dt.date == hoy]
                        df = df.drop(columns=["fecha_dt"])

                    if not df.empty:
                        if "precio" in df.columns:
                            df["precio"] = pd.to_numeric(df["precio"], errors="coerce").fillna(0)
                            df["precio"] = df["precio"].apply(lambda x: f"${x:,.2f}")
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("No hay gastos registrados para el día de hoy.")
                else:
                    st.info("No hay registros en la tabla de gastos.")
            except Exception as e:
                st.error(f"Error al cargar gastos: {e}")

        elif sub_opcion == "Registro de pagos de gastos":
            st.subheader("💳 Registro de Pagos de Gastos")
            try:
                res = supabase.table("gastos").select("*").range(0, 9999).execute()
                df = pd.DataFrame(res.data)
                if not df.empty:
                    df.columns = df.columns.str.lower()
                    if "precio" in df.columns:
                        df["precio"] = pd.to_numeric(df["precio"], errors="coerce").fillna(0)
                        df["precio"] = df["precio"].apply(lambda x: f"${x:,.2f}")
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No hay pagos de gastos registrados.")
            except Exception as e:
                st.error(f"Error al cargar pagos de gastos: {e}")

        elif sub_opcion == "Reporte de gastos (Diario, Semanal, Mensual)":
            st.subheader("📊 Reporte de Gastos")
            tipo_reporte = st.selectbox("Selecciona el periodo del reporte:", ["Diario", "Semanal", "Mensual"], key="reporte_gastos_select")
            
            try:
                res = supabase.table("gastos").select("*").range(0, 9999).execute()
                df = pd.DataFrame(res.data)
                if not df.empty:
                    df.columns = df.columns.str.lower()
                    if "fecha" in df.columns:
                        df["fecha_dt"] = pd.to_datetime(df["fecha"], errors="coerce").dt.tz_localize(None)
                        ahora = pd.Timestamp.now()

                        if tipo_reporte == "Diario":
                            target_fecha = ahora.date()
                            df = df[df["fecha_dt"].dt.date == target_fecha]
                        elif tipo_reporte == "Semanal":
                            inicio_semana = (ahora - pd.Timedelta(days=ahora.dayofweek)).normalize()
                            fin_semana = inicio_semana + pd.Timedelta(days=6, hours=23, minutes=59, seconds=59)
                            df = df[(df["fecha_dt"] >= inicio_semana) & (df["fecha_dt"] <= fin_semana)]
                        elif tipo_reporte == "Mensual":
                            df = df[(df["fecha_dt"].dt.year == ahora.year) & (df["fecha_dt"].dt.month == ahora.month)]

                        df = df.drop(columns=["fecha_dt"])

                    if not df.empty:
                        if "precio" in df.columns:
                            df["precio"] = pd.to_numeric(df["precio"], errors="coerce").fillna(0)
                            total_gastos = df["precio"].sum()
                            df["precio"] = df["precio"].apply(lambda x: f"${x:,.2f}")
                        else:
                            total_gastos = 0

                        st.metric(label=f"Total Gastos ({tipo_reporte})", value=f"${total_gastos:,.2f}")
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info(f"No hay registros de gastos para el reporte {tipo_reporte.lower()}.")
                else:
                    st.info("No hay datos disponibles en gastos.")
            except Exception as e:
                st.error(f"Error al generar reporte de gastos: {e}")

    elif seccion == "Control de Inventario":
        st.title("📦 Sección: Control de Inventario")
        st.markdown("Gestiona el stock actual, las alertas de bajo stock y los productos próximos a vencer.")
        try:
            res = supabase.table("productos").select("*").order("CODIGO").range(0, 9999).execute()
            df = pd.DataFrame(res.data)
            if not df.empty:
                df.columns = df.columns.str.lower()
                
                tab1, tab2, tab3 = st.tabs(["📋 Inventario General", "⚠️ Alertas de Bajo Stock", "⏳ Próximos a Vencer"])
                
                with tab1:
                    st.subheader("Stock Actual de Productos")
                    if "precio venta" in df.columns:
                        df["precio venta"] = pd.to_numeric(df["precio venta"], errors="coerce").fillna(0).apply(lambda x: f"${x:,.2f}")
                    st.dataframe(df, use_container_width=True)
                
                with tab2:
                    st.subheader("Productos con Bajo Stock")
                    col_stock = "stock actual" if "stock actual" in df.columns else None
                    col_min = "stock minimo" if "stock minimo" in df.columns else None
                    
                    if col_stock and col_min:
                        df[col_stock] = pd.to_numeric(df[col_stock], errors="coerce").fillna(0)
                        df[col_min] = pd.to_numeric(df[col_min], errors="coerce").fillna(0)
                        
                        df_bajo_stock = df[df[col_stock] <= df[col_min]]
                        if not df_bajo_stock.empty:
                            st.warning("⚠️ Los siguientes productos están por debajo del stock mínimo:")
                            st.dataframe(df_bajo_stock, use_container_width=True)
                        else:
                            st.success("¡Excelente! No hay productos con bajo stock.")
                    else:
                        st.info(f"Columnas disponibles en la tabla: {list(df.columns)}")
                
                with tab3:
                    st.subheader("Productos Próximos a Vencer (Margen de 20 días)")
                    col_venc = "fecha vencimiento" if "fecha vencimiento" in df.columns else None
                    
                    if col_venc:
                        df["vencimiento date"] = pd.to_datetime(df[col_venc], errors="coerce").dt.date
                        hoy_date = pd.Timestamp.now().date()
                        limite_date = hoy_date + pd.Timedelta(days=20)
                        
                        df_por_vencer = df[(df["vencimiento date"] >= hoy_date) & (df["vencimiento date"] <= limite_date)]
                        
                        if not df_por_vencer.empty:
                            st.error(f"🚨 Productos próximos a vencer entre {hoy_date} y {limite_date}:")
                            st.dataframe(df_por_vencer.drop(columns=["vencimiento date"]), use_container_width=True)
                        else:
                            st.info(f"No hay productos por vencer entre {hoy_date} y {limite_date}.")
                    else:
                        st.info("No se encontró la columna de fecha de vencimiento.")
            else:
                st.info("No hay productos registrados en el inventario.")
        except Exception as e:
            st.error(f"Error al cargar el inventario: {e}")

    elif seccion == "Reportes":
        st.title("📊 Sección: Reportes Financieros")
        st.markdown("Informes organizados para ayudar a tomar decisiones y conocer la salud del negocio.")
        st.markdown("---")

        tipo_reporte_gerencial = st.selectbox(
            "Selecciona el reporte financiero que deseas consultar:",
            [
                "Flujo de Caja",
                "Reporte de Cuentas por Cobrar",
                "Reporte de Cuentas por Pagar",
                "Estado de Resultado"
            ]
        )

        periodo_filtro = st.radio("Periodo de análisis:", ["Diario", "Semanal", "Mensual", "Histórico General"], horizontal=True)

        def filtrar_por_periodo(df_in, col_fecha="fecha"):
            if df_in.empty or col_fecha not in df_in.columns:
                return df_in
            df_copia = df_in.copy()
            df_copia["_dt"] = pd.to_datetime(df_copia[col_fecha], errors="coerce").dt.tz_localize(None)
            ahora = pd.Timestamp.now()
            
            if periodo_filtro == "Diario":
                df_copia = df_copia[df_copia["_dt"].dt.date == ahora.date()]
            elif periodo_filtro == "Semanal":
                inicio_semana = (ahora - pd.Timedelta(days=ahora.dayofweek)).normalize()
                fin_semana = inicio_semana + pd.Timedelta(days=6, hours=23, minutes=59, seconds=59)
                df_copia = df_copia[(df_copia["_dt"] >= inicio_semana) & (df_copia["_dt"] <= fin_semana)]
            elif periodo_filtro == "Mensual":
                df_copia = df_copia[(df_copia["_dt"].dt.year == ahora.year) & (df_copia["_dt"].dt.month == ahora.month)]
            
            return df_copia.drop(columns=["_dt"], errors="ignore")

        try:
            # -----------------------------------------------------------------
            # 1. FLUJO DE CAJA
            # -----------------------------------------------------------------
            if tipo_reporte_gerencial == "Flujo de Caja":
                st.subheader("💵 Reporte de Flujo de Caja")
                st.markdown("Muestra el dinero efectivo que entra y sale del negocio.")

                res_v = supabase.table("ventas").select("*").range(0, 9999).execute()
                res_c = supabase.table("compras").select("*").range(0, 9999).execute()
                res_g = supabase.table("gastos").select("*").range(0, 9999).execute()

                df_v = filtrar_por_periodo(pd.DataFrame(res_v.data))
                df_c = filtrar_por_periodo(pd.DataFrame(res_c.data))
                df_g = filtrar_por_periodo(pd.DataFrame(res_g.data))

                # Normalizar nombres de columnas a minúsculas
                for d in [df_v, df_c, df_g]:
                    if not d.empty:
                        d.columns = d.columns.str.lower()

                # Ingresos en efectivo
                ingresos_efectivo = 0
                if not df_v.empty and "forma de pago" in df_v.columns and "cantidad" in df_v.columns and "precio" in df_v.columns:
                    df_v["cantidad"] = pd.to_numeric(df_v["cantidad"], errors="coerce").fillna(0)
                    df_v["precio"] = pd.to_numeric(df_v["precio"], errors="coerce").fillna(0)
                    mask_efectivo = df_v["forma de pago"].astype(str).str.lower().str.contains("efectivo|nequi|Nequi", na=False)
                    ingresos_efectivo = (df_v.loc[mask_efectivo, "cantidad"] * df_v.loc[mask_efectivo, "precio"]).sum()

                # Compras pagadas en efectivo
                compras_efectivo = 0
                if not df_c.empty and "forma de pago" in df_c.columns and "cantidad" in df_c.columns and "precio" in df_c.columns:
                    df_c["cantidad"] = pd.to_numeric(df_c["cantidad"], errors="coerce").fillna(0)
                    df_c["precio"] = pd.to_numeric(df_c["precio"], errors="coerce").fillna(0)
                    mask_efectivo_c = df_c["forma de pago"].astype(str).str.lower().str.contains("efectivo|nequi|Nequi", na=False)
                    compras_efectivo = (df_c.loc[mask_efectivo_c, "cantidad"] * df_c.loc[mask_efectivo_c, "precio"]).sum()

                # Gastos pagados en efectivo
                gastos_efectivo = 0
                if not df_g.empty and "forma de pago" in df_g.columns and "precio" in df_g.columns:
                    df_g["precio"] = pd.to_numeric(df_g["precio"], errors="coerce").fillna(0)
                    mask_efectivo_g = df_g["forma de pago"].astype(str).str.lower().str.contains("efectivo|nequi|Nequi", na=False)
                    gastos_efectivo = df_g.loc[mask_efectivo_g, "precio"].sum()

                total_caja = ingresos_efectivo - compras_efectivo - gastos_efectivo

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("(+) Ingresos en Efectivo", f"${ingresos_efectivo:,.2f}")
                    st.metric("(-) Compras en Efectivo", f"${compras_efectivo:,.2f}")
                    st.metric("(-) Gastos en Efectivo", f"${gastos_efectivo:,.2f}")
                with col2:
                    st.metric("💰 Total Neto en Caja", f"${total_caja:,.2f}")

            # -----------------------------------------------------------------
            # 2. CUENTAS POR COBRAR
            # -----------------------------------------------------------------
            elif tipo_reporte_gerencial == "Reporte de Cuentas por Cobrar":
                st.subheader("📋 Reporte de Cuentas por Cobrar")
                st.markdown("Valores que los clientes deben al negocio por ventas realizadas a crédito.")

                res_abonos = supabase.table("abonos").select("*").range(0, 9999).execute()
                df_abonos = pd.DataFrame(res_abonos.data)

                if not df_abonos.empty:
                    df_abonos.columns = df_abonos.columns.str.lower()
                    if "monto" in df_abonos.columns:
                        df_abonos["monto"] = pd.to_numeric(df_abonos["monto"], errors="coerce").fillna(0)
                        total_por_cobrar = df_abonos["monto"].sum()
                        st.metric("Total por Cobrar (Abonos registrados)", f"${total_por_cobrar:,.2f}")
                        
                        df_mostrar = df_abonos.copy()
                        df_mostrar["monto"] = df_mostrar["monto"].apply(lambda x: f"${x:,.2f}")
                        st.dataframe(df_mostrar, use_container_width=True)
                    else:
                        st.dataframe(df_abonos, use_container_width=True)
                else:
                    st.info("No hay registros de cuentas por cobrar o abonos pendientes.")

            # -----------------------------------------------------------------
            # 3. CUENTAS POR PAGAR
            # -----------------------------------------------------------------
            elif tipo_reporte_gerencial == "Reporte de Cuentas por Pagar":
                st.subheader("📑 Reporte de Cuentas por Pagar")
                st.markdown("Deudas pendientes con proveedores o servicios recibidos.")

                res_prov = supabase.table("pagos_proveedores").select("*").range(0, 9999).execute()
                df_prov = pd.DataFrame(res_prov.data)

                if not df_prov.empty:
                    df_prov.columns = df_prov.columns.str.lower()
                    if "monto" in df_prov.columns:
                        df_prov["monto"] = pd.to_numeric(df_prov["monto"], errors="coerce").fillna(0)
                        total_por_pagar = df_prov["monto"].sum()
                        st.metric("Total por Pagar a Proveedores", f"${total_por_pagar:,.2f}")

                        df_mostrar = df_prov.copy()
                        df_mostrar["monto"] = df_mostrar["monto"].apply(lambda x: f"${x:,.2f}")
                        st.dataframe(df_mostrar, use_container_width=True)
                    else:
                        st.dataframe(df_prov, use_container_width=True)
                else:
                    st.info("No hay registros de cuentas por pagar a proveedores.")

            # -----------------------------------------------------------------
            # 4. ESTADO DE RESULTADO
            # -----------------------------------------------------------------
            elif tipo_reporte_gerencial == "Estado de Resultado":
                st.subheader("📈 Estado de Resultados (Utilidad o Pérdida)")
                st.markdown("Resumen de ingresos totales, costos y gastos del periodo seleccionado.")

                res_v = supabase.table("ventas").select("*").range(0, 9999).execute()
                res_c = supabase.table("compras").select("*").range(0, 9999).execute()
                res_g = supabase.table("gastos").select("*").range(0, 9999).execute()

                df_v = filtrar_por_periodo(pd.DataFrame(res_v.data))
                df_c = filtrar_por_periodo(pd.DataFrame(res_c.data))
                df_g = filtrar_por_periodo(pd.DataFrame(res_g.data))

                for d in [df_v, df_c, df_g]:
                    if not d.empty:
                        d.columns = d.columns.str.lower()

                # Total Ingresos
                total_ingresos = 0
                if not df_v.empty and "cantidad" in df_v.columns and "precio" in df_v.columns:
                    df_v["cantidad"] = pd.to_numeric(df_v["cantidad"], errors="coerce").fillna(0)
                    df_v["precio"] = pd.to_numeric(df_v["precio"], errors="coerce").fillna(0)
                    total_ingresos = (df_v["cantidad"] * df_v["precio"]).sum()

                # Total Costos (Basado en las compras totales de mercancía)
                total_costos = 0
                if not df_c.empty and "cantidad" in df_c.columns and "precio" in df_c.columns:
                    df_c["cantidad"] = pd.to_numeric(df_c["cantidad"], errors="coerce").fillna(0)
                    df_c["precio"] = pd.to_numeric(df_c["precio"], errors="coerce").fillna(0)
                    total_costos = (df_c["cantidad"] * df_c["precio"]).sum()

                # Total Gastos
                total_gastos = 0
                if not df_g.empty and "precio" in df_g.columns:
                    df_g["precio"] = pd.to_numeric(df_g["precio"], errors="coerce").fillna(0)
                    total_gastos = df_g["precio"].sum()

                utilidad_neta = total_ingresos - total_costos - total_gastos

                st.metric("(+) Total Ingresos", f"${total_ingresos:,.2f}")
                st.metric("(-) Total Costos", f"${total_costos:,.2f}")
                st.metric("(-) Total Gastos", f"${total_gastos:,.2f}")
                
                st.markdown("---")
                if utilidad_neta >= 0:
                    st.success(f"🎉 **Utilidad Neta del Periodo:** ${utilidad_neta:,.2f}")
                else:
                    st.error(f"⚠️ **Pérdida Neta del Periodo:** ${utilidad_neta:,.2f}")

        except Exception as e:
            st.error(f"Error al generar los reportes gerenciales: {e}")