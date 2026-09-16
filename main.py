import socket
import sqlite3

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pandas as pd
import psutil

from ping3 import ping
from scapy.all import ARP, Ether, srp

from fabricantes import FABRICANTES


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

    conexion = sqlite3.connect(
        "inventario.db"
    )

    cursor = conexion.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS escaneos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            interfaz TEXT,
            red TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dispositivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            escaneo_id INTEGER,
            ip TEXT,
            hostname TEXT,
            mac TEXT,
            fabricante TEXT,
            FOREIGN KEY (escaneo_id)
            REFERENCES escaneos(id)
        )
    """)

    conexion.commit()
    conexion.close()
def crear_escaneo(
    interfaz,
    red
):

    conexion = sqlite3.connect(
        "inventario.db"
    )

    cursor = conexion.cursor()

    fecha = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    cursor.execute(
        """
        INSERT INTO escaneos(
            fecha,
            interfaz,
            red
        )
        VALUES (?, ?, ?)
        """,
        (
            fecha,
            interfaz,
            red
        )
    )

    escaneo_id = cursor.lastrowid

    conexion.commit()
    conexion.close()

    return escaneo_id

def guardar_en_bd(
    escaneo_id,
    dispositivos
):

    conexion = sqlite3.connect(
        "inventario.db"
    )

    cursor = conexion.cursor()

    for dispositivo in dispositivos:

        cursor.execute(
            """
            INSERT INTO dispositivos
            (
                escaneo_id,
                ip,
                hostname,
                mac,
                fabricante
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                escaneo_id,
                dispositivo["IP"],
                dispositivo["HOSTNAME"],
                dispositivo["MAC"],
                dispositivo["FABRICANTE"]
            )
        )

    conexion.commit()
    conexion.close()

def obtener_ips_ultimo_escaneo():

    conexion = sqlite3.connect(
        "inventario.db"
    )

    cursor = conexion.cursor()

    cursor.execute("""
        SELECT id
        FROM escaneos
        ORDER BY id DESC
        LIMIT 2
    """)

    escaneos = cursor.fetchall()

    if len(escaneos) < 2:

        conexion.close()

        return set()

    escaneo_anterior = escaneos[1][0]

    cursor.execute("""
        SELECT ip
        FROM dispositivos
        WHERE escaneo_id = ?
    """, (escaneo_anterior,))

    resultado = {
        fila[0]
        for fila in cursor.fetchall()
    }

    conexion.close()

    return resultado

def detectar_nuevos(dispositivos):

    ips_anteriores = (
        obtener_ips_ultimo_escaneo()
    )

    return [

        dispositivo

        for dispositivo in dispositivos

        if dispositivo["IP"]
        not in ips_anteriores
    ]

def obtener_redes():

    redes = []

    for interfaz, direcciones in psutil.net_if_addrs().items():

        if any(
            palabra in interfaz.lower()
            for palabra in INTERFACES_EXCLUIDAS
        ):
            continue

        for direccion in direcciones:

            if direccion.family == socket.AF_INET:

                ip = direccion.address

                if (
                    ip.startswith("127.")
                    or ip.startswith("169.254.")
                ):
                    continue

                redes.append(
                    {
                        "interfaz": interfaz,
                        "ip": ip
                    }
                )

    return redes


def seleccionar_red():

    redes = obtener_redes()

    if not redes:

        print(
            "No se encontraron interfaces válidas."
        )

        raise SystemExit

    print("\nInterfaces disponibles:\n")

    for indice, red in enumerate(
        redes,
        start=1
    ):

        print(
            f"{indice}. "
            f"{red['interfaz']} -> "
            f"{red['ip']}"
        )

    while True:

        try:

            opcion = int(
                input(
                    "\nSelecciona una interfaz: "
                )
            )

            if 1 <= opcion <= len(redes):
                break

            print(
                "Opción no válida."
            )

        except ValueError:

            print(
                "Introduce un número."
            )

    seleccionada = redes[
        opcion - 1
    ]

    ip_local = seleccionada["ip"]

    red = ".".join(
        ip_local.split(".")[:3]
    )

    return (
    seleccionada["interfaz"],
    ip_local,
    red
)


def obtener_hostname(ip):

    try:
        return socket.gethostbyaddr(ip)[0]

    except Exception:
        return "Desconocido"


def obtener_mac(ip):

    try:

        paquete = (
            Ether(
                dst="ff:ff:ff:ff:ff:ff"
            )
            /
            ARP(pdst=ip)
        )

        resultado = srp(
            paquete,
            timeout=1,
            verbose=False
        )[0]

        if resultado:

            return (
                resultado[0][1]
                .hwsrc
                .upper()
            )

    except Exception:
        pass

    return "Desconocida"


def obtener_fabricante(mac):

    if mac == "Desconocida":
        return "Desconocido"

    prefijo = mac[0:8]

    return FABRICANTES.get(
        prefijo,
        "Desconocido"
    )


def escanear_ip(ip):

    try:

        respuesta = ping(
            ip,
            timeout=0.1
        )

        if respuesta:

            hostname = obtener_hostname(
                ip
            )

            mac = obtener_mac(
                ip
            )

            fabricante = (
                obtener_fabricante(
                    mac
                )
            )

            print(
                f"✅ {ip} | "
                f"{hostname} | "
                f"{mac} | "
                f"{fabricante}"
            )

            return {
                "IP": ip,
                "HOSTNAME": hostname,
                "MAC": mac,
                "FABRICANTE": fabricante
            }

    except Exception:
        pass

    return None


def escanear_red(red):

    dispositivos = []

    ips = [
        f"{red}.{i}"
        for i in range(1, 255)
    ]

    with ThreadPoolExecutor(
        max_workers=100
    ) as executor:

        resultados = list(
            executor.map(
                escanear_ip,
                ips
            )
        )

    for resultado in resultados:

        if resultado:

            dispositivos.append(
                resultado
            )

    return dispositivos


def exportar_excel(dispositivos):

    if not dispositivos:

        return None

    fecha_hora = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    nombre_archivo = (
        f"inventario_{fecha_hora}.xlsx"
    )

    df = pd.DataFrame(
        dispositivos
    )

    df.sort_values(
        by="IP"
    ).to_excel(
        nombre_archivo,
        index=False
    )

    return nombre_archivo


def mostrar_estadisticas(dispositivos):

    fabricantes = {}

    for dispositivo in dispositivos:

        fabricante = dispositivo[
            "FABRICANTE"
        ]

        fabricantes[
            fabricante
        ] = (
            fabricantes.get(
                fabricante,
                0
            ) + 1
        )

    print(
        "\nFabricantes encontrados:\n"
    )

    for fabricante, cantidad in sorted(
        fabricantes.items()
    ):

        print(
            f"{fabricante}: "
            f"{cantidad}"
        )


def main():

    crear_base_datos()

    print("=" * 60)
    print("INVENTARIO DE RED V6")
    print("=" * 60)

    interfaz, ip_local, red = seleccionar_red()

    print(
        f"\nIP seleccionada: "
        f"{ip_local}"
    )

    print(
        f"Red detectada: "
        f"{red}.0/24"
    )

    dispositivos = escanear_red(
        red
    )
    escaneo_id = crear_escaneo(
    interfaz,
    red
    )

    if not dispositivos:

        print(
            "\nNo se encontraron dispositivos."
        )

        return

    nuevos = detectar_nuevos(
        dispositivos
    )

    guardar_en_bd(
    escaneo_id,
    dispositivos
    )

    archivo = exportar_excel(
        dispositivos
    )

    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)

    print(
        f"Dispositivos encontrados: "
        f"{len(dispositivos)}"
    )

    print(
        f"Dispositivos nuevos: "
        f"{len(nuevos)}"
    )

    if nuevos:

        print(
            "\nNuevos dispositivos:"
        )

        for dispositivo in nuevos:

            print(
                f"- {dispositivo['IP']} "
                f"({dispositivo['HOSTNAME']})"
            )

    mostrar_estadisticas(
        dispositivos
    )

    print(
        f"\nExcel generado: "
        f"{archivo}"
    )

    print(
        "Base de datos: inventario.db"
    )


if __name__ == "__main__":
    main()