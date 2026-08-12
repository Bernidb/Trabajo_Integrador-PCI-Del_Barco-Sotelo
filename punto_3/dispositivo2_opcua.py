import asyncio
from asyncua import Server
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusIOException

PUERTO_COM = 'COM4'
ID_ESCLAVO = 1
DIRECCION_INICIO = 0
CANTIDAD_REGISTROS = 3

OPC_ENDPOINT = "opc.tcp://0.0.0.0:4840/freeopcua/server/"
OPC_NAMESPACE = "http://unraf.edu.ar/modbus_opcua/"

stats = {"DONE": 0, "CRC_ERROR": 0, "DEVICE_NOT_REACHED": 0}

async def main():
    server = Server()
    await server.init()
    server.set_endpoint(OPC_ENDPOINT)
    server.set_server_name("Dispositivo_2_Bridge_OPCUA")
    
    idx = await server.register_namespace(OPC_NAMESPACE)
    objects = server.nodes.objects
    nodo_modbus = await objects.add_folder(idx, "Sistema_Modbus_RTU")

    var_potenciometro = await nodo_modbus.add_variable(idx, "Potenciometro", 0)
    var_luz = await nodo_modbus.add_variable(idx, "Sensor_Luz", 0)
    var_boton = await nodo_modbus.add_variable(idx, "Boton", 0)
    
    var_stats_done = await nodo_modbus.add_variable(idx, "Stats_DONE", 0)
    var_stats_crc = await nodo_modbus.add_variable(idx, "Stats_CRC_Error", 0)
    var_stats_reached = await nodo_modbus.add_variable(idx, "Stats_Not_Reached", 0)

    # NUEVO: Nodos para recibir comandos desde arriba y hacerlos escribibles
    var_cmd_digital = await nodo_modbus.add_variable(idx, "Cmd_Digital", False)
    var_cmd_analogico = await nodo_modbus.add_variable(idx, "Cmd_Analogico", 0)
    await var_cmd_digital.set_writable()
    await var_cmd_analogico.set_writable()

    print(f"--- SERVIDOR OPC UA LEVANTADO EN: {OPC_ENDPOINT} ---")

    modbus_client = ModbusSerialClient(port=PUERTO_COM, baudrate=9600, bytesize=8, parity='N', stopbits=1, timeout=1)
    if not modbus_client.connect():
        print("[FATAL] No se pudo abrir el puerto COM.")
        return

    # Variables para detectar si hubo un cambio desde la web
    estado_digital_ant = False
    estado_analogico_ant = 0

    async with server:
        try:
            while True:
                # 1. LEER COMANDOS OPC UA Y MANDAR POR MODBUS
                cmd_dig = await var_cmd_digital.read_value()
                cmd_ana = await var_cmd_analogico.read_value()

                if cmd_dig != estado_digital_ant:
                    # Escribe un Coil (Funcion 0x05)
                    modbus_client.write_coil(address=0, value=cmd_dig, device_id=ID_ESCLAVO)
                    estado_digital_ant = cmd_dig
                    print(f"> Comando Modbus: Salida Digital -> {cmd_dig}")
                
                if cmd_ana != estado_analogico_ant:
                    # Escribe un Registro (Funcion 0x06)
                    modbus_client.write_register(address=0, value=cmd_ana, device_id=ID_ESCLAVO)
                    estado_analogico_ant = cmd_ana
                    print(f"> Comando Modbus: Salida Analogica -> {cmd_ana}")

                # 2. ADQUISICION DE DATOS ESTANDAR
                respuesta = modbus_client.read_input_registers(address=DIRECCION_INICIO, count=CANTIDAD_REGISTROS, device_id=ID_ESCLAVO)

                if respuesta.isError():
                    if isinstance(respuesta, ModbusIOException):
                        stats["DEVICE_NOT_REACHED"] += 1
                    else:
                        stats["CRC_ERROR"] += 1
                else:
                    stats["DONE"] += 1
                    valores = respuesta.registers
                    await var_potenciometro.write_value(valores[0])
                    await var_luz.write_value(valores[1])
                    await var_boton.write_value(valores[2])

                await var_stats_done.write_value(stats["DONE"])
                await var_stats_crc.write_value(stats["CRC_ERROR"])
                await var_stats_reached.write_value(stats["DEVICE_NOT_REACHED"])

                await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass
        finally:
            modbus_client.close()

if __name__ == "__main__":
    asyncio.run(main())