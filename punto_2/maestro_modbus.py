import time
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusIOException

# =========================================================
# CONFIGURACIÓN DEL MAESTRO MODBUS
# =========================================================
PUERTO_COM = 'COM4'  # <-- El puerto del adaptador USB (el chupete)
ID_ESCLAVO = 1
DIRECCION_INICIO = 0
CANTIDAD_REGISTROS = 3 # Potenciómetro, Luz, Botón

# =========================================================
# CONTADORES ESTADÍSTICOS (Requisito de la Cátedra)
# =========================================================
stats = {
    "DONE": 0,               # Trama enviada, recibida y válida
    "CRC_ERROR": 0,          # Trama recibida rota o error matemático
    "DEVICE_NOT_REACHED": 0  # El esclavo no respondió a tiempo
}

# Inicializamos el cliente Modbus RTU
client = ModbusSerialClient(
    port=PUERTO_COM,
    baudrate=9600,
    bytesize=8,
    parity='N',
    stopbits=1,
    timeout=1  # 1 segundo de espera máxima 
)

def imprimir_estadisticas():
    print(f"ESTADÍSTICAS DE RED -> DONE: {stats['DONE']} | CRC ERROR: {stats['CRC_ERROR']} | NO REACHED: {stats['DEVICE_NOT_REACHED']}")
    print("-" * 70)

if client.connect():
    print(f"--- CONECTADO AL PUERTO {PUERTO_COM} ---")
    print("Iniciando interrogación cíclica al Esclavo...")
    print("=" * 70)
    
    try:
        while True:
            # Enviamos la petición: Función 0x04 (Read Input Registers)
            respuesta = client.read_input_registers(
                address=DIRECCION_INICIO, 
                count=CANTIDAD_REGISTROS, 
                device_id=ID_ESCLAVO
            )

            # Clasificamos el estado de la respuesta para la estadística
            if respuesta.isError():
                if isinstance(respuesta, ModbusIOException):
                    stats["DEVICE_NOT_REACHED"] += 1
                    print("[ERROR] Timeout: El esclavo no responde.")
                else:
                    stats["CRC_ERROR"] += 1
                    print(f"[ERROR] Trama corrupta o excepción: {respuesta}")
            else:
                stats["DONE"] += 1
                valores = respuesta.registers
                print(f"[OK] Datos recibidos -> Potenciómetro: {valores[0]} | Luz: {valores[1]} | Botón: {valores[2]}")

            imprimir_estadisticas()
            
            # Pausa de 1 segundo antes de volver a preguntar
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[!] Programa detenido por el usuario.")
    finally:
        client.close()
        print("Puerto COM liberado.")
else:
    print(f"[FATAL] No se pudo abrir el puerto {PUERTO_COM}. ¿Está el QModMaster abierto?")