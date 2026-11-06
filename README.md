# Monitoreo de Humedad de Suelo con Nodos WiFi

**Autores:** Carlos Andrés Erazo Garzón · Jaime Enrique Pedraza Suárez
**Curso:** Sistemas Embebidos — Pontificia Universidad Javeriana — Semestre 2026-3

## Descripción del proyecto

Sistema de monitoreo de humedad de suelo con **4 nodos inalámbricos** (2× Particle
Argon, 2× Particle Photon 2), cada uno con varios sensores capacitivos **HW-390** a
distintas profundidades. Cada nodo mide y publica por **WiFi/MQTT** directo —sin nube 
de terceros— a una **Particle Tachyon** que actúa como
broker, almacén y servidor local, evaluando alertas de riego por umbral de humedad.

## Arquitectura (diagrama de bloques)

```
 HW-390 x4            HW-390 x4            HW-390 x3            HW-390 x3
 (A0,A1,A2,A5)        (A0,A1,A2,A5)        (A0,A1,A2)           (A0,A1,A2)
      |                     |                    |                    |
      v                     v                    v                    v
[Particle Argon]      [Particle Argon]    [Particle Photon 2]  [Particle Photon 2]
   nodoA                  nodoB                nodoC                nodoD
 (ARG_NODE_A)           (ARG_NODE_B)          (P2_NODE_A)          (P2_NODE_B)
      |                     |                    |                    |
      +---------------------+------- WiFi --------+--------------------+
                                      |
                        Router WiFi local (TP-Link TL-WR1502X,
                               sin salida a internet)
                                      |
                                      v
                    +--------------------------------------+
                    |   Particle Tachyon (Ubuntu 24.04)     |
                    |                                       |
                    |  Mosquitto (broker MQTT :1883)        |
                    |              |                        |
                    |              v                        |
                    |  core/mqtt_listener.py                |
                    |  (mosquitto_sub -> cola interna)       |
                    |              |                        |
                    |              v                        |
                    |  main.py (hilo principal = procesa)    |
                    |    - core/storage.py   (SQLite)        |
                    |    - core/alerts.py    (umbral humedad)|
                    |    - core/forwarder.py (reenvio HTTPS) |
                    |              |                        |
                    |              v                        |
                    |  api/server.py  (HTTP :5001)           |
                    |   GET /status  GET /lectura            |
                    |   GET /history GET /alarmas            |
                    +--------------------------------------+
                                      |
                          (sin internet en el sitio de la
                           demo: forwarder queda inactivo)
                                      v
                              Plataforma web (futuro)
```

## Hardware

### Componentes

| Componente | Referencia | Función |
|---|---|---|
| Sensor de humedad | Capacitivo HW-390 v2 (×14) | Humedad del suelo, salida analógica |
| Nodo (×2) | Particle Argon | MCU + WiFi (nRF52840 + coprocesador ESP32) |
| Nodo (×2) | Particle Photon 2 | MCU + WiFi (RTL872x) |
| Servidor local | Particle Tachyon | Broker, almacenamiento, API, alertas |
| Red | TP-Link TL-WR1502X | WiFi local, sin salida a internet en el sitio |

### Conexiones GPIO (todas iguales: `VCC→3V3`, `GND→GND`, `AOUT→pin`)

| Nodo | Placa | Pines usados | Profundidades |
|---|---|---|---|
| nodoA | Particle Argon (ARG_NODE_A) | A0, A1, A2, A5 | 5 / 15 / 30 / 45 cm |
| nodoB | Particle Argon (ARG_NODE_B) | A0, A1, A2, A5 | 5 / 15 / 30 / 45 cm |
| nodoC | Particle Photon 2 (P2_NODE_A) | A0, A1, A2 | 5 / 15 / 30 cm |
| nodoD | Particle Photon 2 (P2_NODE_B) | A0, A1, A2 | 5 / 15 / 30 cm |

El Photon 2 no expone A5 de forma confiable entre modelos, por eso solo usa 3 canales.

## Software

### Estructura del repositorio

```
particle-nodes/
  nodoA/, nodoB/, nodoC/, nodoD/   Firmware Particle (Device OS, C++) de cada nodo
  tachyon/                         Backend que corre en la Particle Tachyon
    main.py                        Punto de entrada, orquesta los hilos
    config.json                    Config: broker, umbrales de alerta, puertos
    core/
      mqtt_listener.py             Hilo MQTT -> cola interna
      storage.py                   SQLite
      alerts.py                    Evaluación de umbral de humedad
      forwarder.py                 Reenvío HTTPS a plataforma (best-effort)
      logger.py                    Logging rotativo (10 MB)
    api/server.py                  API REST local
    systemd/suelo.service          Unidad systemd para correr como servicio
```

### Lenguajes y librerías

| Componente | Lenguaje | Librerías |
|---|---|---|
| Firmware nodos | C++ (Particle Device OS, estilo Arduino) | `MQTT` (TCP, sin nube de Particle) |
| Backend Tachyon | Python 3 | **solo librería estándar** |

**Nota importante:** el backend usa deliberadamente solo librería estándar de Python
(`sqlite3`, `json`, `http.server`, `urllib`, `subprocess`, `threading`, `logging`) en vez
de `paho-mqtt`/`Flask`/`PyYAML`. La Tachyon, en el sitio de la demo, está en una red WiFi
sin salida a internet, así que no se puede garantizar `pip install` ni `apt install` de
nada que no viniera ya en el sistema. El hilo MQTT reutiliza el binario `mosquitto_sub`
(de `mosquitto-clients`, que sí se alcanzó a instalar con internet) en vez de una
librería cliente; la API usa `http.server` en vez de Flask, con los mismos 4 endpoints.

### Hilos del servicio (`tachyon/main.py`)

- **Hilo MQTT** (`mqtt_listener`): `mosquitto_sub -t 'suelo/#'` → cola interna.
- **Hilo de API** (`api_flask_like`): sirve `/status`, `/lectura`, `/history`, `/alarmas`.
- **Hilo de reenvío** (`forwarder`): best-effort HTTPS hacia la plataforma web.
- **Hilo principal**: toma de la cola, guarda en SQLite, evalúa alertas, encola reenvío.

### Endpoints locales

- `GET /status` — estado del servicio, uptime, total de lecturas, nodos vistos.
- `GET /lectura` — última lectura de cada nodo.
- `GET /history?desde=&hasta=&node=` — histórico filtrable por tiempo (epoch) y nodo.
- `GET /alarmas` — alertas activas (umbral de humedad baja/crítica).

## Comunicación

- **Nodo → Tachyon:** MQTT 3.1.1 sobre WiFi, puerto 1883, sin TLS (red local aislada).
- **Tópico:** `suelo/{nodo}-s{indice}/lectura`, ej. `suelo/nodoA-s0/lectura`.
- **Payload:**
  ```json
  {"node": "nodoA-s0", "profundidad": "5cm", "raw": 2150, "humedad_pct": 58}
  ```
- **Tachyon → Plataforma:** REST/HTTPS, deshabilitado en `config.json` mientras no haya
  internet en el sitio (`"plataforma": {"habilitado": false}`).

## Cómo correrlo

### Nodos (firmware)
```bash
cd nodoA   # o nodoB, nodoC, nodoD
particle compile argon .   --saveTo firmware.bin   # argon para nodoA/B
particle compile p2 .      --saveTo firmware.bin   # p2 para nodoC/D
particle flash --usb firmware.bin
```

### Backend (en la Tachyon)
```bash
scp -r tachyon root@<IP_TACHYON>:/root/suelo-service
ssh root@<IP_TACHYON>
cd /root/suelo-service
python3 main.py                      # prueba en primer plano
# si funciona, instalarlo como servicio:
cp systemd/suelo.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now suelo.service
systemctl status suelo.service
```

## Pruebas realizadas

- Cada nodo se validó individualmente: flasheo por USB, confirmación de publicación
  MQTT con `mosquitto_sub -t 'suelo/#' -v` en la Tachyon.
- Verificación de inserción en SQLite para cada nodo (`GET /lectura` muestra las 4
  entradas con sus respectivos sub-sensores).
- Prueba de reconexión WiFi/MQTT tras reinicio de nodo.

## Estado actual

- ✅ Mosquitto corriendo y expuesto en la LAN de la Tachyon.
- ✅ Los 4 nodos (14 sensores) flasheados, conectados y publicando.
- ✅ Backend completo desplegado: SQLite, alertas, API REST, logging rotativo.
- ⬜ Calibración fina de 2 puntos (aire/agua) por sensor.
- ⬜ Reenvío a la plataforma web (pendiente de internet en el sitio).
