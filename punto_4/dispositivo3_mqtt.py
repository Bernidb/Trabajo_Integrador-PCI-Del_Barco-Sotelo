import asyncio
import json
import paho.mqtt.client as mqtt
from asyncua import Client

OPC_URL = "opc.tcp://127.0.0.1:4840/freeopcua/server/"
OPC_NAMESPACE = "http://unraf.edu.ar/modbus_opcua/"

BROKER_MQTT = "test.mosquitto.org"
PUERTO_MQTT = 1883
TOPIC_TELEMETRIA = "grupo_tp/telemetria/sensores"
TOPIC_STATS = "grupo_tp/telemetria/estadisticas"
TOPIC_COMANDOS = "grupo_tp/comandos/salidas"

# Variable global para comunicar el hilo de MQTT con el hilo principal
comando_recibido = None

# Configuracion del cliente MQTT
def on_connect(client, userdata, flags, rc):
    # Ahora nos suscribimos a los comandos que vienen de la web
    client.subscribe(TOPIC_COMANDOS)
    print("Suscrito al topic de comandos en la nube.")

def on_message(client, userdata, msg):
    global comando_recibido
    try:
        comando_recibido = json.loads(msg.payload.decode())
    except:
        pass

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

async def main():
    global comando_recibido
    mqtt_client.connect(BROKER_MQTT, PUERTO_MQTT, 60)
    mqtt_client.loop_start()

    print(f"Conectando al Servidor OPC UA en {OPC_URL} ...")
    async with Client(url=OPC_URL) as opc_client:
        idx = await opc_client.get_namespace_index(OPC_NAMESPACE)

        # Mapeo de nodos de lectura
        nodo_pot = await opc_client.nodes.root.get_child(["0:Objects", f"{idx}:Sistema_Modbus_RTU", f"{idx}:Potenciometro"])
        nodo_luz = await opc_client.nodes.root.get_child(["0:Objects", f"{idx}:Sistema_Modbus_RTU", f"{idx}:Sensor_Luz"])
        nodo_boton = await opc_client.nodes.root.get_child(["0:Objects", f"{idx}:Sistema_Modbus_RTU", f"{idx}:Boton"])
        
        nodo_done = await opc_client.nodes.root.get_child(["0:Objects", f"{idx}:Sistema_Modbus_RTU", f"{idx}:Stats_DONE"])
        nodo_crc = await opc_client.nodes.root.get_child(["0:Objects", f"{idx}:Sistema_Modbus_RTU", f"{idx}:Stats_CRC_Error"])
        nodo_not_reached = await opc_client.nodes.root.get_child(["0:Objects", f"{idx}:Sistema_Modbus_RTU", f"{idx}:Stats_Not_Reached"])

        # NUEVO: Mapeo de nodos de escritura
        nodo_cmd_digital = await opc_client.nodes.root.get_child(["0:Objects", f"{idx}:Sistema_Modbus_RTU", f"{idx}:Cmd_Digital"])
        nodo_cmd_analogico = await opc_client.nodes.root.get_child(["0:Objects", f"{idx}:Sistema_Modbus_RTU", f"{idx}:Cmd_Analogico"])

        try:
            while True:
                # 1. BAJADA: Ver si llego un comando por MQTT y escribirlo en OPC UA
                if comando_recibido:
                    if comando_recibido["tipo"] == "digital":
                        valor_bool = True if comando_recibido["valor"] == 255 else False
                        await nodo_cmd_digital.write_value(valor_bool)
                    elif comando_recibido["tipo"] == "analogico":
                        await nodo_cmd_analogico.write_value(comando_recibido["valor"])
                    
                    comando_recibido = None # Limpiamos para no reenviar lo mismo

                # 2. SUBIDA: Leer OPC UA y mandar a MQTT
                pot = await nodo_pot.read_value()
                luz = await nodo_luz.read_value()
                boton = await nodo_boton.read_value()

                payload_sensores = json.dumps({"potenciometro": pot, "luz": luz, "boton": boton})
                payload_stats = json.dumps({
                    "DONE": await nodo_done.read_value(), 
                    "CRC_ERROR": await nodo_crc.read_value(), 
                    "NOT_REACHED": await nodo_not_reached.read_value()
                })

                mqtt_client.publish(TOPIC_TELEMETRIA, payload_sensores)
                mqtt_client.publish(TOPIC_STATS, payload_stats)
                
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass
        finally:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())