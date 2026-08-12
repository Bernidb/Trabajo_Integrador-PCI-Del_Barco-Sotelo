import asyncio
import serial
import struct
import time
from asyncua import Server

# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================
PUERTO_COM = 'COM4'
ID_ESCLAVO = 1

OPC_ENDPOINT = "opc.tcp://0.0.0.0:4840/freeopcua/server/"
OPC_NAMESPACE = "http://unraf.edu.ar/modbus_opcua/"

stats = {"DONE": 0, "CRC_ERROR": 0, "DEVICE_NOT_REACHED": 0}

# =========================================================
# MODBUS ARTESANAL (Reemplazo de pymodbus)
# =========================================================
def calcular_crc(datos):
    """
    Implementación matemática del algoritmo CRC-16 estandar para Modbus.
    Recorre cada byte y aplica los shifts lógicos y la compuerta XOR con 0xA001.
    """
    crc = 0xFFFF
    for byte in datos:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    # Empaqueta el entero de 16 bits en 2 bytes Little Endian (Low Byte primero)
    return struct.pack('<H', crc)

def enviar_y_recibir(puerto, trama_sin_crc, bytes_esperados):
    """
    Une la trama con su CRC, la manda al cable de cobre y lee la respuesta.
    """
    trama_completa = trama_sin_crc + calcular_crc(trama_sin_crc)
    
    # Limpiamos basura del buffer y transmitimos
    puerto.reset_input_buffer()
    puerto.write(trama_completa)
    
    # Esperamos el tiempo necesario para que lleguen los bytes
    respuesta = puerto.read(bytes_esperados)
    
    # 1. Validamos Timeout
    if len(respuesta) < 4: # Mínimo necesario: ID, Función y 2 bytes de CRC
        return "TIMEOUT", None
        
    # 2. Validamos Integridad (CRC)
    crc_recibido = respuesta[-2:]
    crc_calculado = calcular_crc(respuesta[:-2])
    
    if crc_recibido != crc_calculado:
        return "CRC_ERROR", None
        
    # 3. Retornamos éxito y la trama pura
    return "OK", respuesta

# =========================================================
# SERVIDOR OPC UA Y BUCLE PRINCIPAL
# =========================================================
async def main():
    # Inicialización estándar de OPC UA
    server = Server()
    await server.init()
    server.set_endpoint(OPC_ENDPOINT)
    server.set_server_name("Dispositivo_2_Bridge_OPCUA")
    
    idx = await server.register_namespace(OPC_NAMESPACE)
    objects = server.nodes.objects
    nodo_modbus = await objects.add_folder(idx, "Sistema_Modbus_RTU")

    var_pot = await nodo_modbus.add_variable(idx, "Potenciometro", 0)
    var_luz = await nodo_modbus.add_variable(idx, "Sensor_Luz", 0)
    var_boton = await nodo_modbus.add_variable(idx, "Boton", 0)
    
    var_stats_done = await nodo_modbus.add_variable(idx, "Stats_DONE", 0)
    var_stats_crc = await nodo_modbus.add_variable(idx, "Stats_CRC_Error", 0)
    var_stats_nr = await nodo_modbus.add_variable(idx, "Stats_Not_Reached", 0)

    var_cmd_digital = await nodo_modbus.add_variable(idx, "Cmd_Digital", False)
    var_cmd_analogico = await nodo_modbus.add_variable(idx, "Cmd_Analogico", 0)
    await var_cmd_digital.set_writable()
    await var_cmd_analogico.set_writable()

    print(f"--- SERVIDOR OPC UA LEVANTADO EN: {OPC_ENDPOINT} ---")

    # Inicializamos la variable del puerto serial en None
    puerto_serial = None
    estado_digital_ant = False
    estado_analogico_ant = 0

    async with server:
        try:
            while True:
                # -----------------------------------------------------------
                # CONTROL DE HARDWARE: Reconexión Automática del USB
                # -----------------------------------------------------------
                if puerto_serial is None or not puerto_serial.is_open:
                    try:
                        puerto_serial = serial.Serial(port=PUERTO_COM, baudrate=9600, timeout=1.0)
                        print(f"--- PUERTO SERIAL {PUERTO_COM} CONECTADO ---")
                    except serial.SerialException:
                        # Si no encuentra el USB, marca error y espera antes de reintentar
                        print(f"[FALLA FÍSICA] Adaptador USB no detectado en {PUERTO_COM}. Reintentando...")
                        stats["DEVICE_NOT_REACHED"] += 1
                        await var_stats_nr.write_value(stats["DEVICE_NOT_REACHED"])
                        await asyncio.sleep(2)
                        continue

                try:
                    # -----------------------------------------------------------
                    # 1. BAJADA DE COMANDOS (Escribir al Arduino)
                    # -----------------------------------------------------------
                    cmd_dig = await var_cmd_digital.read_value()
                    cmd_ana = await var_cmd_analogico.read_value()

                    if cmd_dig != estado_digital_ant:
                        valor_modbus = 0xFF00 if cmd_dig else 0x0000
                        trama = struct.pack('>BBHH', ID_ESCLAVO, 0x05, 0x0000, valor_modbus)
                        enviar_y_recibir(puerto_serial, trama, 8)
                        estado_digital_ant = cmd_dig
                        print(f"> Comando: Salida Digital -> {cmd_dig}")
                    
                    if cmd_ana != estado_analogico_ant:
                        trama = struct.pack('>BBHH', ID_ESCLAVO, 0x06, 0x0000, cmd_ana)
                        enviar_y_recibir(puerto_serial, trama, 8)
                        estado_analogico_ant = cmd_ana
                        print(f"> Comando: Salida Analógica -> {cmd_ana}")

                    # -----------------------------------------------------------
                    # 2. ADQUISICIÓN DE DATOS (Interrogar al Arduino)
                    # -----------------------------------------------------------
                    trama_peticion = struct.pack('>BBHH', ID_ESCLAVO, 0x04, 0x0000, 3)
                    
                    estado, respuesta = enviar_y_recibir(puerto_serial, trama_peticion, 11)

                    if estado == "TIMEOUT":
                        stats["DEVICE_NOT_REACHED"] += 1
                        print("[ERROR] Timeout: Capa física desconectada.")
                    elif estado == "CRC_ERROR":
                        stats["CRC_ERROR"] += 1
                        print("[ERROR] Fallo CRC: Ruido electromagnético en la línea.")
                    elif estado == "OK":
                        stats["DONE"] += 1
                        
                        datos_puros = respuesta[3:9]
                        pot, luz, boton = struct.unpack('>HHH', datos_puros)
                        
                        await var_pot.write_value(pot)
                        await var_luz.write_value(luz)
                        await var_boton.write_value(boton)

                    # Publicamos contadores de diagnóstico de red
                    await var_stats_done.write_value(stats["DONE"])
                    await var_stats_crc.write_value(stats["CRC_ERROR"])
                    await var_stats_nr.write_value(stats["DEVICE_NOT_REACHED"])

                except serial.SerialException:
                    # Si el cable USB se desconecta justo mientras leía o escribía
                    print("[CRÍTICO] El adaptador USB fue desconectado de la PC.")
                    if puerto_serial:
                        puerto_serial.close()
                    puerto_serial = None

                await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass
        finally:
            if puerto_serial and puerto_serial.is_open:
                puerto_serial.close()
            print("Puerto Serial Liberado.")

if __name__ == "__main__":
    asyncio.run(main())