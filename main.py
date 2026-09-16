import socket
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import psutil
from ping3 import ping


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
                        "ip": ip,
                    }
                )

    return redes


def seleccionar_red():

    redes = obtener_redes()

    if not redes:

        print("No se encontraron interfaces válidas.")
        exit()

    print("\nInterfaces disponibles:\n")

    for indice, red in enumerate(redes, start=1):

        print(
            f"{indice}. "
            f"{red['interfaz']} -> "
            f"{red['ip']}"
        )

    opcion = int(
        input(
            "\nSeleccione una interfaz: "
        )
    )

    seleccionada = redes[opcion - 1]

    ip_local = seleccionada["ip"]

    red = ".".join(
        ip_local.split(".")[:3]
    )

    return ip_local, red


def obtener_hostname(ip):

    try:
        return socket.gethostbyaddr(ip)[0]

    except:
        return "Desconocido"


def escanear_ip(ip):

    try:

        respuesta = ping(
            ip,
            timeout=0.05
        )

        if respuesta:

            hostname = obtener_hostname(ip)

            print(
                f"✅ {ip} - {hostname}"
            )

            return {
                "IP": ip,
                "HOSTNAME": hostname,
            }

    except:
        pass

    return None


def escanear_red(red):

    dispositivos = []

    lista_ips = [
        f"{red}.{i}"
        for i in range(1, 255)
    ]

    with ThreadPoolExecutor(
        max_workers=100
    ) as executor:

        resultados = executor.map(
            escanear_ip,
            lista_ips
        )

        for resultado in resultados:

            if resultado:
                dispositivos.append(
                    resultado
                )

    return dispositivos


def exportar_excel(dispositivos):

    nombre_archivo = (
        "inventario.xlsx"
    )

    df = pd.DataFrame(
        dispositivos
    )

    df.to_excel(
        nombre_archivo,
        index=False
    )

    return nombre_archivo


def main():

    print("=" * 60)
    print("INVENTARIO DE RED")
    print("=" * 60)

    ip_local, red = seleccionar_red()

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
        f"Excel generado: "
        f"{archivo}"
    )


if __name__ == "__main__":
    main()