#include "MQTT.h"
SYSTEM_MODE(SEMI_AUTOMATIC); SYSTEM_THREAD(ENABLED);

const char* NODE_ID    = "nodoC";
byte MQTT_BROKER_IP[]  = {192,168,0,47};
const int   MQTT_PORT  = 1883;

const int   N_SENSORES = 3;
const int   PINES[]    = {A0, A1, A2};
const char* PROFUND[]  = {"5cm","15cm","30cm"};

// Calibracion por sensor (6 nov, lecturas en seco, promediadas 15 muestras):
const int RAW_SECO[]   = {3346, 3292, 3318};  // medido en seco
const int RAW_MOJADO[] = {1546, 1492, 1518};  // ESTIMADO: seco - 1800 (swing tipico HW-390), sin verificar con agua todavia

const int MUESTRAS_ADC    = 15;  // lecturas promediadas por sensor, por ciclo
const int DELAY_MUESTRA_MS = 3;  // separacion entre muestras

void callback(char* t, byte* p, unsigned int l) {}
MQTT client(MQTT_BROKER_IP, MQTT_PORT, callback);

int leerPromediado(int pin) {
  long suma = 0;
  for (int i = 0; i < MUESTRAS_ADC; i++) {
    suma += analogRead(pin);
    delay(DELAY_MUESTRA_MS);
  }
  return suma / MUESTRAS_ADC;
}

void setup() {
  WiFi.on(); WiFi.connect(); waitUntil(WiFi.ready);
  client.connect(NODE_ID);
}

void loop() {
  if (!client.isConnected()) client.connect(NODE_ID);
  client.loop();
  for (int i = 0; i < N_SENSORES; i++) {
    int raw = leerPromediado(PINES[i]);
    int pct = map(constrain(raw, RAW_MOJADO[i], RAW_SECO[i]), RAW_SECO[i], RAW_MOJADO[i], 0, 100);
    char id[24]; snprintf(id, sizeof(id), "%s-s%d", NODE_ID, i);
    char msg[128], topic[64];
    snprintf(msg, sizeof(msg), "{\"node\":\"%s\",\"profundidad\":\"%s\",\"raw\":%d,\"humedad_pct\":%d}",
             id, PROFUND[i], raw, pct);
    snprintf(topic, sizeof(topic), "suelo/%s/lectura", id);
    client.publish(topic, msg);
    delay(50);
  }
  delay(10000);
}
