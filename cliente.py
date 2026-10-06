import re
from getpass import getpass

import requests

# Configuración de la conexión con la API
BASE_URL = "http://127.0.0.1:5000"
TIMEOUT = 5  # segundos de espera máxima por respuesta

# Session mantiene la cookie que devuelve /login y la reenvía en los pedidos siguientes
sesion = requests.Session()


def pedir_credenciales():
    # Pide usuario y contraseña por consola y arma el JSON que espera la API
    usuario = input("Usuario: ").strip()
    contrasenia = getpass("Contraseña: ")  # no muestra lo que se escribe
    return {"usuario": usuario, "contraseña": contrasenia}


def enviar(metodo, ruta, **kwargs):
    # Hace el pedido HTTP y maneja el caso de que el servidor no esté disponible
    try:
        return sesion.request(metodo, BASE_URL + ruta, timeout=TIMEOUT, **kwargs)
    except requests.exceptions.ConnectionError:
        print("No se pudo conectar al servidor. Verificá que esté en ejecución.")
    except requests.exceptions.Timeout:
        print("El servidor tardó demasiado en responder.")
    return None


def mostrar_json(respuesta):
    # Las respuestas de /registro y /login son JSON con "mensaje" o "error"
    try:
        datos = respuesta.json()
    except ValueError:
        print(f"[{respuesta.status_code}] Respuesta inesperada del servidor.")
        return
    print(f"[{respuesta.status_code}] {datos.get('mensaje') or datos.get('error')}")


def registrar():
    # Opción 1: crea un usuario nuevo
    respuesta = enviar("POST", "/registro", json=pedir_credenciales())
    if respuesta is not None:
        mostrar_json(respuesta)


def iniciar_sesion():
    # Opción 2: inicia sesión; la cookie queda guardada en el objeto Session
    respuesta = enviar("POST", "/login", json=pedir_credenciales())
    if respuesta is not None:
        mostrar_json(respuesta)


def ver_tareas():
    # Opción 3: pide /tareas con la cookie de sesión (si no hay sesión el servidor responde 401)
    respuesta = enviar("GET", "/tareas")
    if respuesta is None:
        return

    if respuesta.status_code == 200:
        # /tareas devuelve HTML: se sacan las etiquetas para mostrarlo en consola
        texto = re.sub(r"<[^>]+>", " ", respuesta.text.split("</title>")[-1])
        print(f"[200] {' '.join(texto.split())}")
    else:
        mostrar_json(respuesta)


# Opciones del menú: número, texto a mostrar y función que se ejecuta
OPCIONES = {
    "1": ("Registrarse", registrar),
    "2": ("Iniciar sesión", iniciar_sesion),
    "3": ("Ver tareas", ver_tareas),
}


def menu():
    # Muestra el menú en bucle hasta que el usuario elige la opción 4
    while True:
        print("\n=== Gestión de Tareas ===")
        for clave, (nombre, _) in OPCIONES.items():
            print(f"{clave}. {nombre}")
        print("4. Salir")

        opcion = input("Opción: ").strip()
        if opcion == "4":
            break
        if opcion in OPCIONES:
            OPCIONES[opcion][1]()
        else:
            print("Opción inválida.")


if __name__ == "__main__":
    menu()
