// =================================================================
// CÓDIGO FINAL - Modbus RTU Estándar + RS485 Half-Duplex
// =================================================================
const int PIN_SALIDA_DIGITAL = 8;
const int PIN_SALIDA_ANALOGICA = 9;
const int PIN_POTENCIOMETRO = A0;
const int PIN_SENSOR_LUZ = A1;
const int PIN_ENTRADA_DIGITAL = 7;
const int PIN_LED_TEST = 13; 
const int PIN_RS485_CTRL = 2; // Pin de control DE/RE para el MAX485

byte buffer[16];

void setup() {
  Serial.begin(9600);
  Serial.setTimeout(100); 
  
  pinMode(PIN_SALIDA_DIGITAL, OUTPUT);
  pinMode(PIN_SALIDA_ANALOGICA, OUTPUT);
  pinMode(PIN_ENTRADA_DIGITAL, INPUT); 
  pinMode(PIN_LED_TEST, OUTPUT);

  // Configuramos el bus RS485 para que arranque en modo RECEPCIÓN
  pinMode(PIN_RS485_CTRL, OUTPUT);
  digitalWrite(PIN_RS485_CTRL, LOW);
}

void loop() {
  if (Serial.available() > 0) {
    int len = Serial.readBytes(buffer, 8); 
    
    // Limpiamos el buffer por si entró ruido en la línea RS485
    while(Serial.available() > 0) { Serial.read(); }

    if (len == 8 && buffer[0] == 0x01) {
        
        uint16_t checksum = calcularCRCModbus(buffer, 6);
        uint8_t crc_low = checksum & 0xFF;
        uint8_t crc_high = checksum >> 8;

        if (buffer[6] == crc_low && buffer[7] == crc_high) {
            
            digitalWrite(PIN_LED_TEST, HIGH); 

            if (buffer[1] == 0x04) {
                byte tramaRespuesta[11]; 
                tramaRespuesta[0] = 0x01;
                tramaRespuesta[1] = 0x04;
                tramaRespuesta[2] = 0x06; 
                
                int valorPot = analogRead(PIN_POTENCIOMETRO);
                int valorLuz = analogRead(PIN_SENSOR_LUZ);
                int ent_dig = digitalRead(PIN_ENTRADA_DIGITAL);
                
                tramaRespuesta[3] = highByte(valorPot);
                tramaRespuesta[4] = lowByte(valorPot);
                tramaRespuesta[5] = highByte(valorLuz);
                tramaRespuesta[6] = lowByte(valorLuz);
                tramaRespuesta[7] = 0x00;           
                tramaRespuesta[8] = ent_dig;        
                
                enviarRespuestaConCRC(tramaRespuesta, 9);
            }
            else if (buffer[1] == 0x05) {
                if (buffer[4] == 0xFF) digitalWrite(PIN_SALIDA_DIGITAL, HIGH);
                else if (buffer[4] == 0x00) digitalWrite(PIN_SALIDA_DIGITAL, LOW);
                enviarRespuestaConCRC(buffer, 6);
            }
            else if (buffer[1] == 0x06) {
                analogWrite(PIN_SALIDA_ANALOGICA, buffer[5]);
                enviarRespuestaConCRC(buffer, 6);
            }
            digitalWrite(PIN_LED_TEST, LOW); 
        } 
    } 
  }
}

// --- Función de envío con control de flujo RS485 ---
void enviarRespuestaConCRC(byte* datos, int dataLenSinCrc) {
  uint16_t checksum = calcularCRCModbus(datos, dataLenSinCrc);
  datos[dataLenSinCrc] = checksum & 0xFF;
  datos[dataLenSinCrc + 1] = checksum >> 8;
  
  // Silencio Modbus normativo y tiempo para que el USB pase a RX
  delay(10); 
  
  digitalWrite(PIN_RS485_CTRL, HIGH); // Habilitamos la TRANSMISIÓN
  delay(2); // Estabilización del chip MAX485
  
  Serial.write(datos, dataLenSinCrc + 2);
  Serial.flush(); // CLAVE: Bloquea hasta que se envía el último bit
  
  digitalWrite(PIN_RS485_CTRL, LOW);  // Volvemos a modo RECEPCIÓN
}
// --- Algoritmo Matemático Estándar Modbus RTU CRC-16 ---
uint16_t calcularCRCModbus(byte *datos, int longitud) {
  uint16_t crc = 0xFFFF;
  for (int pos = 0; pos < longitud; pos++) {
    crc ^= (uint16_t)datos[pos];    
    for (int i = 8; i != 0; i--) {  
      if ((crc & 0x0001) != 0) {    
        crc >>= 1;                  
        crc ^= 0xA001;              
      } else {                        
        crc >>= 1;                  
      }
    }
  }
  return crc;
}