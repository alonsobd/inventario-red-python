from concurrent.futures import ThreadPoolExecutor, as_completed
from ping3 import ping

import ipaddress
import pandas as pd
import psutil
import socket
import logging
import time


# ==================================================
# CONFIGURACIÓN
# ==================================================

MAX_THREADS = 100
EXCEL_FILE = "inventario.xlsx"
LOG_FILE = "inventario.log"


# ==================================================
# LOGGING
# ==================================================

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# ==================================================
# REDES
# ==================================================

def obtener_redes():
    """
    Detecta todas las redes IPv4 activas.
    """

    redes = []

    interfaces = psutil.net_if_addrs()

    for nombre, direcciones in interfaces.items():

        for direccion in direcciones:

            if direccion.family == socket.AF_INET:

                ip = direccion.address
                mascara = direccion.netmask

                if not mascara:
                    continue

                try:

                    red = ipaddress.IPv4Network(
                        f"{ip}/{mascara}",
                        strict=False
                    )

                    redes.append(
                        {
                            "interfaz": nombre,
                            "ip": ip,
                            "red": red
                        }
                    )

                except Exception as error:

                    logging.warning(
                        f"Error procesando interfaz "
                        f"{nombre}: {error}"
                    )

    return redes


# ==================================================
# HOSTNAME
# ==================================================

def obtener_hostname(ip):

    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return "Desconocido"


# ==================================================
# PING
# ==================================================

def comprobar_host(ip):

    try:

        respuesta = ping(
            str(ip),
            timeout=0.5
        )

        if respuesta:

            hostname = obtener_hostname(str(ip))

            return {
                "IP": str(ip),
                "HOSTNAME": hostname
            }

    except Exception:
        pass

    return None


# ==================================================
# ESCANEO
# ==================================================

def escanear_red(red):

    dispositivos = []

    hosts = list(red.hosts())

    print(f"\nEscaneando red {red}")

    with ThreadPoolExecutor(
        max_workers=MAX_THREADS
    ) as executor:

        futuras = {
            executor.submit(
                comprobar_host,
                host
            ): host
            for host in hosts
        }

        for tarea in as_completed(futuras):

            resultado = tarea.result()

            if resultado:

                dispositivos.append(resultado)

                print(
                    f"✅ {resultado['IP']} - "
                    f"{resultado['HOSTNAME']}"
                )

    return dispositivos


# ==================================================
# EXCEL
# ==================================================

def exportar_excel(dispositivos):

    df = pd.DataFrame(dispositivos)

    if len(df) == 0:

        print("\nNo se encontraron dispositivos")

        return

    df = df.sort_values(
        by=["IP"]
    )

    df.to_excel(
        EXCEL_FILE,
        index=False
    )

    print(
        f"\nExcel generado: "
        f"{EXCEL_FILE}"
    )


# ==================================================
# MAIN
# ==================================================

def main():

    inicio = time.time()

    print("=" * 60)
    print("INVENTARIO DE RED")
    print("=" * 60)

    logging.info(
        "Inicio de escaneo"
    )

    redes = obtener_redes()

    if not redes:

        print(
            "No se encontraron "
            "redes activas"
        )

        return

    print("\nRedes detectadas:\n")

    for red in redes:

        print(
            f"{red['interfaz']} -> "
            f"{red['red']}"
        )

    dispositivos_totales = []

    for red in redes:

        try:

            encontrados = escanear_red(
                red["red"]
            )

            dispositivos_totales.extend(
                encontrados
            )

        except Exception as error:

            logging.error(
                f"Error escaneando "
                f"{red['red']}: {error}"
            )

    # Eliminar duplicados

    unicos = {}

    for dispositivo in dispositivos_totales:

        unicos[
            dispositivo["IP"]
        ] = dispositivo

    dispositivos_totales = list(
        unicos.values()
    )

    exportar_excel(
        dispositivos_totales
    )

    fin = time.time()

    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)

    print(
        f"Dispositivos encontrados: "
        f"{len(dispositivos_totales)}"
    )

    print(
        f"Tiempo empleado: "
        f"{round(fin - inicio, 2)} segundos"
    )

    logging.info(
        f"Escaneo finalizado. "
        f"{len(dispositivos_totales)} "
        f"equipos encontrados."
    )


if __name__ == "__main__":
    main()