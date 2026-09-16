import socket
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import psutil
from ping3 import ping
from scapy.all import ARP, Ether, srp


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
    """
    Obtiene las interfaces IPv4 válidas.
    """

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
        print("No se han encontrado interfaces válidas.")
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
            "\nSelecciona una interfaz: "
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


def obtener_mac(ip):

    try:

        paquete = (
            Ether(
                dst="ff:ff:ff:ff:ff:ff"
            )
            /
            ARP(
                pdst=ip
            )
        )

        resultado = srp(
            paquete,
            timeout=1,
            verbose=False
        )[0]

        if resultado:

            return resultado[0][1].hwsrc

    except:
        pass

    return "Desconocida"


def escanear_ip(ip):

    try:

        respuesta = ping(
            ip,
            timeout=0.05
        )

        if respuesta:

            hostname = obtener_hostname(ip)
            mac = obtener_mac(ip)

            print(
                f"✅ {ip} | "
                f"{hostname} | "
                f"{mac}"
            )

            return {
                "IP": ip,
                "HOSTNAME": hostname,
                "MAC": mac,
            }

    except:
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


def mostrar_resumen(dispositivos):

    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)

    print(
        f"Dispositivos encontrados: "
        f"{len(dispositivos)}"
    )


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

    mostrar_resumen(
        dispositivos
    )

    print(
        f"\nExcel generado: "
        f"{archivo}"
    )


if __name__ == "__main__":
    main()