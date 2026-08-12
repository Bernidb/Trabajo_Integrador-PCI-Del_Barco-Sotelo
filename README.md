# Sistema SCADA IoT: Modbus RTU, OPC UA y MQTT

Proyecto integrador para la validación de arquitecturas de red multicapa, desarrollado para la cátedra de Protocolos de Comunicaciones Industriales (Ingeniería en Computación).

**Autores:** 
* Bernardo Del Barco
* Juan Cruz Sotelo

---

## Estructura del Proyecto

El repositorio está organizado en base a los incisos de la consigna de la cátedra:

    📁 Trabajo_Integrador-PCI-Del_Barco-Sotelo
    ├── 📁 punto_1
    │   └── 📁 punto1
    │       └── 📄 punto1.ino
    ├── 📁 punto_2
    │   └── 📄 maestro_modbus.py
    ├── 📁 punto_3
    │   └── 📄 dispositivo2_opcua_amano.py
    ├── 📁 punto_4
    │   └── 📄 dispositivo3_mqtt.py
    ├── 📄 .gitignore
    ├── 📄 dashboard.py
    ├── 📄 README.md
    ├── 📄 requirements.txt
    └── 📄 Tarea_3_Trabajo_integrador_V25.pdf

### Descripción de Archivos

* **`punto_1/punto1/punto1.ino`**: Código C++ (Firmware) para el microcontrolador (Esclavo Modbus RTU). Administra la capa física (RS485), lee los sensores analógicos/digitales, controla el actuador (LED PWM) y procesa las peticiones Modbus.
* **`punto_2/maestro_modbus.py`**: Implementación base del Maestro Modbus para interrogación de registros.
* **`punto_3/dispositivo2_opcua_amano.py`**: Núcleo de la capa de enlace. Actúa como Maestro Modbus RTU generando las tramas a bajo nivel (con cálculo matemático del CRC-16) y, en paralelo, levanta el Servidor OPC UA local en memoria RAM para estandarizar las variables físicas. Incluye lógica de reconexión automática ante desconexiones de hardware (USB).
* **`punto_4/dispositivo3_mqtt.py`**: Gateway de comunicación a la nube (Cliente OPC UA a MQTT). Se suscribe al servidor local, empaqueta la telemetría en JSON y la publica en un Broker MQTT, a la vez que escucha comandos externos para bajarlos a la capa física.
* **`dashboard.py`**: Interfaz SCADA bidireccional (HMI) desarrollada con Streamlit. Permite la visualización de datos, actuación remota y monitoreo en tiempo real de las estadísticas y diagnósticos de la red.
* **`Tarea_3_Trabajo_integrador_V25.pdf`**: Documento con la consigna original de la cátedra.

---

## Requisitos de Instalación

1. Clonar el repositorio en tu máquina local.
2. Crear un entorno virtual (recomendado): 
   python -m venv .venv
3. Activar el entorno virtual y cargar las dependencias exactas:
   pip install -r requirements.txt

## Ejecución del Sistema

Para levantar la arquitectura completa, se requieren tres instancias de terminal corriendo en paralelo en la raíz del proyecto:

1. Levantar la capa física y estandarización OPC UA:
   python punto_3/dispositivo2_opcua_amano.py

2. Levantar el puente a la nube MQTT:
   python punto_4/dispositivo3_mqtt.py

3. Levantar la interfaz SCADA:
   python -m streamlit run dashboard.py