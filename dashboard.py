import streamlit as st
import paho.mqtt.client as mqtt
import json
import time

# =========================================================
# CONFIGURACION MQTT
# =========================================================
BROKER = "test.mosquitto.org"
PORT = 1883
TOPIC_SENSORES = "grupo_tp/telemetria/sensores"
TOPIC_STATS = "grupo_tp/telemetria/estadisticas"
TOPIC_COMANDOS = "grupo_tp/comandos/salidas"

# =========================================================
# MEMORIA COMPARTIDA ENTRE HILOS
# =========================================================
# Usamos cache_resource para que el diccionario sobreviva a las 
# recargas de la pagina y ambos hilos puedan leer/escribir el mismo objeto.
@st.cache_resource
def obtener_memoria_compartida():
    return {
        "sensores": {"potenciometro": 0, "luz": 0, "boton": 0},
        "stats": {"DONE": 0, "CRC_ERROR": 0, "NOT_REACHED": 0},
        "last_update": 0
    }

datos_red = obtener_memoria_compartida()

# =========================================================
# INICIALIZACION DEL CLIENTE MQTT
# =========================================================
@st.cache_resource
def iniciar_mqtt():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    
    def on_connect(client, userdata, flags, rc):
        client.subscribe(TOPIC_SENSORES)
        client.subscribe(TOPIC_STATS)

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            if msg.topic == TOPIC_SENSORES:
                datos_red["sensores"] = payload
                datos_red["last_update"] = time.time()
            elif msg.topic == TOPIC_STATS:
                datos_red["stats"] = payload
        except Exception:
            pass # Si llega basura, se descarta para no crashear

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)
    client.loop_start()
    return client

mqtt_client = iniciar_mqtt()

# =========================================================
# INTERFAZ WEB
# =========================================================
st.set_page_config(page_title="Dashboard SCADA", layout="wide")
st.title("Panel de Control Industrial - Integrador")

# Calculo de timeout: si pasan 3 segs sin datos, marcamos error de conectividad
estado_opcua = "DONE" if (time.time() - datos_red["last_update"] < 3) else "ERROR"

# --- DIAGNOSTICO DE RED ---
st.subheader("Diagnostico de Red")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**Estado OPC UA**")
    if estado_opcua == "DONE":
        st.success("DONE")
    else:
        st.error("ERROR - Falla de conectividad")

with col2:
    st.markdown("**Estadisticas Modbus RTU**")
    st.info(f"DONE: {datos_red['stats'].get('DONE', 0)}")
    st.warning(f"CRC ERROR: {datos_red['stats'].get('CRC_ERROR', 0)}")
    st.error(f"DEVICE NOT REACHED: {datos_red['stats'].get('NOT_REACHED', 0)}")

st.divider()

# --- SENSORES ---
st.subheader("Telemetria del Dispositivo 1")
col_s1, col_s2, col_s3 = st.columns(3)

col_s1.metric("Potenciometro", datos_red["sensores"].get("potenciometro", 0))
col_s2.metric("Sensor de Luz", datos_red["sensores"].get("luz", 0))

estado_boton = "Presionado" if datos_red["sensores"].get("boton", 0) == 1 else "Suelto"
col_s3.metric("Boton", estado_boton)

st.divider()

# --- COMANDOS PARA ENVIAR AL ARDUINO ---
st.subheader("Control de Planta")
col_c1, col_c2 = st.columns(2)

with col_c1:
    salida_digital = st.toggle("Activar Salida Digital (Rele/LED)")
    if st.button("Enviar Comando Digital"):
        valor = 0xFF if salida_digital else 0x00
        mqtt_client.publish(TOPIC_COMANDOS, json.dumps({"tipo": "digital", "valor": valor}))
        st.toast("Comando digital enviado")

with col_c2:
    salida_analogica = st.slider("Salida Analogica (PWM)", 0, 255, 0)
    if st.button("Enviar Comando Analogico"):
        mqtt_client.publish(TOPIC_COMANDOS, json.dumps({"tipo": "analogico", "valor": salida_analogica}))
        st.toast("Comando analogico enviado")

# Refresco automatico
time.sleep(1)
st.rerun()