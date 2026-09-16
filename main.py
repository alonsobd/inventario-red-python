import socket
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pandas as pd
import psutil
from ping3 import ping
from scapy.all import ARP, Ether, conf, srp

conf.use_pcap = False
conf.verb = 0

from fabricantes import FABRICANTES

DB_NAME = "inventario.db"
INTERFACES_EXCLUIDAS = [
    "loopback",
    "cisco",
    "anyconnect",
    "vpn",
    "tailscale",
    "vmware",
    "hyper-v",
    "virtualbox",
    "vethernet",
]


def crear_base_datos():
    with sqlite3.connect(DB_NAME) as conexion:
        cursor = conexion.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS escaneos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT,
                interfaz TEXT,
                red TEXT,
                duracion_segundos REAL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dispositivos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                escaneo_id INTEGER,
                ip TEXT,
                hostname TEXT,
                mac TEXT,
                fabricante TEXT,
                FOREIGN KEY (escaneo_id) REFERENCES escaneos(id)
            )
            """
        )

        columnas = [columna[1] for columna in cursor.execute("PRAGMA table_info(escaneos)").fetchall()]
        if "duracion_segundos" not in columnas:
            cursor.execute("ALTER TABLE escaneos ADD COLUMN duracion_segundos REAL")

        conexion.commit()


def crear_escaneo(interfaz, red, duracion_segundos=0.0):
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_NAME) as conexion:
        cursor = conexion.cursor()
        cursor.execute(
            """
            INSERT INTO escaneos (fecha, interfaz, red, duracion_segundos)
            VALUES (?, ?, ?, ?)
            """,
            (fecha, interfaz, red, duracion_segundos),
        )
        conexion.commit()
        return cursor.lastrowid


def guardar_en_bd(escaneo_id, dispositivos):
    if not dispositivos:
        return

    with sqlite3.connect(DB_NAME) as conexion:
        cursor = conexion.cursor()
        for dispositivo in dispositivos:
            cursor.execute(
                """
                INSERT INTO dispositivos (escaneo_id, ip, hostname, mac, fabricante)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    escaneo_id,
                    dispositivo["IP"],
                    dispositivo["HOSTNAME"],
                    dispositivo["MAC"],
                    dispositivo["FABRICANTE"],
                ),
            )
        conexion.commit()


def obtener_ips_ultimo_escaneo():
    with sqlite3.connect(DB_NAME) as conexion:
        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT id
            FROM escaneos
            ORDER BY id DESC
            LIMIT 2
            """
        )
        escaneos = cursor.fetchall()

        if len(escaneos) < 2:
            return set()

        escaneo_anterior_id = escaneos[1][0]
        cursor.execute(
            """
            SELECT ip
            FROM dispositivos
            WHERE escaneo_id = ?
            """,
            (escaneo_anterior_id,),
        )
        return {fila[0] for fila in cursor.fetchall()}


def detectar_nuevos(dispositivos):
    ips_anteriores = obtener_ips_ultimo_escaneo()
    return [
        dispositivo for dispositivo in dispositivos if dispositivo["IP"] not in ips_anteriores
    ]


def detectar_desaparecidos(dispositivos):
    ips_actuales = {dispositivo["IP"] for dispositivo in dispositivos}
    ips_anteriores = obtener_ips_ultimo_escaneo()
    return ips_anteriores - ips_actuales


def obtener_redes():
    redes = []
    for interfaz, direcciones in psutil.net_if_addrs().items():
        if any(palabra in interfaz.lower() for palabra in INTERFACES_EXCLUIDAS):
            continue

        for direccion in direcciones:
            if direccion.family == socket.AF_INET:
                ip = direccion.address
                if ip.startswith("127.") or ip.startswith("169.254."):
                    continue
                redes.append({"interfaz": interfaz, "ip": ip})

    return redes


def seleccionar_red():
    redes = obtener_redes()
    if not redes:
        print("No se encontraron interfaces válidas.")
        raise SystemExit

    if len(redes) == 1:
        seleccionada = redes[0]
        ip_local = seleccionada["ip"]
        red_base = ".".join(ip_local.split(".")[:3])
        return seleccionada["interfaz"], ip_local, red_base

    print("\nInterfaces disponibles:\n")
    for indice, red in enumerate(redes, start=1):
        print(f"{indice}. {red['interfaz']} -> {red['ip']}")

    while True:
        try:
            entrada = input("\nSelecciona una interfaz (pulsa Enter para elegir la 1): ").strip()
            opcion = 1 if entrada == "" else int(entrada)
            if 1 <= opcion <= len(redes):
                break
            print("Opción no válida.")
        except ValueError:
            print("Introduce un número válido.")

    seleccionada = redes[opcion - 1]
    ip_local = seleccionada["ip"]
    red_base = ".".join(ip_local.split(".")[:3])
    return seleccionada["interfaz"], ip_local, red_base


def obtener_hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return "Desconocido"


def obtener_mac(ip):
    try:
        paquete = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=ip)
        ans, _ = srp(paquete, timeout=1.5, verbose=False)
        if ans:
            return ans[0][1].hwsrc.upper()
    except Exception:
        pass
    return "Desconocida"


def obtener_fabricante(mac):
    if mac == "Desconocida":
        return "Desconocido"
    prefijo = mac[:8]
    return FABRICANTES.get(prefijo, "Desconocido")


def escanear_ip(ip):
    try:
        respuesta = ping(ip, timeout=0.2)
        if not respuesta:
            return None

        hostname = obtener_hostname(ip)
        mac = obtener_mac(ip)
        fabricante = obtener_fabricante(mac)

        print(f"✅ {ip} | {hostname} | {mac} | {fabricante}")
        return {
            "IP": ip,
            "HOSTNAME": hostname,
            "MAC": mac,
            "FABRICANTE": fabricante,
        }
    except Exception:
        return None


def escanear_red(red):
    ips = [f"{red}.{i}" for i in range(1, 255)]
    dispositivos = []

    with ThreadPoolExecutor(max_workers=100) as executor:
        resultados = list(executor.map(escanear_ip, ips))

    for resultado in resultados:
        if resultado:
            dispositivos.append(resultado)

    return dispositivos


def exportar_excel(dispositivos):
    if not dispositivos:
        return None

    nombre_archivo = f"inventario_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df = pd.DataFrame(dispositivos)
    df.sort_values(by="IP").to_excel(nombre_archivo, index=False)
    return nombre_archivo


def mostrar_estadisticas(dispositivos):
    fabricantes = {}
    for dispositivo in dispositivos:
        fabricante = dispositivo["FABRICANTE"]
        fabricantes[fabricante] = fabricantes.get(fabricante, 0) + 1

    print("\nFabricantes encontrados:\n")
    for fabricante, cantidad in sorted(fabricantes.items()):
        print(f"{fabricante}: {cantidad}")


def ejecutar_escaneo(red):
    inicio = time.perf_counter()
    dispositivos = escanear_red(red)
    duracion = round(time.perf_counter() - inicio, 2)
    return dispositivos, duracion


def main():
    crear_base_datos()

    print("=" * 60)
    print("INVENTARIO DE RED V9")
    print("=" * 60)

    interfaz, ip_local, red = seleccionar_red()
    print(f"\nIP seleccionada: {ip_local}")
    print(f"Red detectada: {red}.0/24")

    dispositivos, duracion = ejecutar_escaneo(red)
    escaneo_id = crear_escaneo(interfaz, red, duracion)
    guardar_en_bd(escaneo_id, dispositivos)

    nuevos = detectar_nuevos(dispositivos)
    desaparecidos = detectar_desaparecidos(dispositivos)
    archivo = exportar_excel(dispositivos)

    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)

    print(f"Dispositivos encontrados: {len(dispositivos)}")
    print(f"Dispositivos nuevos: {len(nuevos)}")
    print(f"Dispositivos desaparecidos: {len(desaparecidos)}")
    print(f"Duración del escaneo: {duracion} segundos")

    if nuevos:
        print("\nNuevos dispositivos:")
        for dispositivo in nuevos:
            print(f"- {dispositivo['IP']} ({dispositivo['HOSTNAME']})")

    if desaparecidos:
        print("\nDispositivos desaparecidos:")
        for ip in desaparecidos:
            print(f"- {ip}")

    mostrar_estadisticas(dispositivos)

    if archivo:
        print(f"\nExcel generado: {archivo}")

    print("Base de datos: inventario.db")


if __name__ == "__main__":
    main()