from ping3 import ping

ips = [
    "192.168.1.1",
    "192.168.1.10",
    "192.168.1.20"
]

for ip in ips:
    respuesta = ping(ip)

    if respuesta:
        print(f"{ip} ACTIVO")
    else:
        print(f"{ip} NO RESPONDE")