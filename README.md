# Inventario de Red

Proyecto para escanear dispositivos de una red local, guardar el historial en SQLite y visualizar los resultados con Streamlit.

## Características

- Escaneo de red por interfaz
- Detección de dispositivos nuevos y desaparecidos
- Registro de historial en SQLite
- Medición de duración del escaneo
- Exportación a Excel
- Dashboard visual con Streamlit

## Requisitos

- Python 3.11
- Windows
- Acceso a la red local
- Permisos de ARP/escaneo adecuados en el sistema

## Instalación

```bash
py -3.11 -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt