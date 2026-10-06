import os
import secrets
import socket
import sqlite3
import datetime

from flask import Flask, jsonify, redirect, request, session
from markupsafe import escape
from werkzeug.security import generate_password_hash, check_password_hash

# Configuración del servidor y de la base de datos
HOST = "127.0.0.1"
PORT = 5000
DB_NAME = "usuarios.db"

# Configuración de la aplicación Flask
app = Flask(__name__)
# Las respuestas JSON devuelven los acentos y la ñ como caracteres (no como secuencias \uXXXX)
app.json.ensure_ascii = False
# Clave con la que Flask firma la cookie de sesión. Se puede fijar con la variable de
# entorno SECRET_KEY; si no existe se genera una aleatoria (las sesiones no sobreviven al reinicio)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))


# Plantilla HTML de los formularios que se usan desde el navegador (registro y login).
# Los marcadores __X__ se reemplazan en pagina_formulario()
FORMULARIO = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>__TITULO__</title>
    <style>
        body { font-family: sans-serif; max-width: 360px; margin: 3rem auto; }
        input, button { display: block; width: 100%; margin: 0.5rem 0; padding: 0.5rem; box-sizing: border-box; }
    </style>
</head>
<body>
    <h1>__TITULO__</h1>
    <form id="formulario">
        <input id="usuario" placeholder="Usuario" required>
        <input id="contrasenia" type="password" placeholder="Contraseña" required>
        <button type="submit">__BOTON__</button>
    </form>
    <p id="mensaje"></p>
    <p><a href="__ENLACE__">__TEXTO_ENLACE__</a></p>
    <script>
        // Envía las credenciales como JSON al endpoint POST y muestra la respuesta del servidor
        const destino = "__DESTINO__";
        document.getElementById("formulario").addEventListener("submit", async (evento) => {
            evento.preventDefault();
            const respuesta = await fetch("__RUTA__", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({
                    usuario: document.getElementById("usuario").value,
                    "contraseña": document.getElementById("contrasenia").value
                })
            });
            const datos = await respuesta.json();
            document.getElementById("mensaje").textContent = datos.mensaje || datos.error;
            if (respuesta.ok) { window.location = destino; }
        });
    </script>
</body>
</html>"""

# Página que ve el navegador al pedir /tareas sin haber iniciado sesión
ACCESO_RESTRINGIDO = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>Acceso restringido</title>
</head>
<body>
    <h1>Acceso restringido</h1>
    <p>Para ver las tareas primero hay que <a href="/login">iniciar sesión</a>.</p>
</body>
</html>"""


def conectar_bd():
    # Abre una conexión nueva por request (sqlite3 no comparte conexiones entre hilos)
    return sqlite3.connect(DB_NAME)


def inicializar_bd():
    # Crea la tabla de usuarios si todavía no existe
    conexion = conectar_bd()
    try:
        with conexion:
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    fecha_registro TEXT NOT NULL
                )
            """)
    finally:
        # el "with" de sqlite3 solo confirma la transacción, la conexión se cierra a mano
        conexion.close()


def leer_credenciales():
    # Devuelve (usuario, contraseña) del JSON recibido, o (None, None) si es inválido
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return None, None

    usuario = datos.get("usuario")
    contrasenia = datos.get("contraseña")
    if not isinstance(usuario, str) or not isinstance(contrasenia, str):
        return None, None

    usuario = usuario.strip()
    if not usuario or not contrasenia:
        return None, None
    return usuario, contrasenia


def pagina_formulario(titulo, boton, ruta, destino, enlace, texto_enlace):
    # Arma la página con el formulario que envía los datos a la ruta POST indicada
    pagina = FORMULARIO
    for marcador, valor in (("__TITULO__", titulo), ("__BOTON__", boton), ("__RUTA__", ruta),
                            ("__DESTINO__", destino), ("__ENLACE__", enlace), ("__TEXTO_ENLACE__", texto_enlace)):
        pagina = pagina.replace(marcador, valor)
    return pagina


# La raíz redirige al formulario de login
@app.route("/", methods=["GET"])
def inicio():
    return redirect("/login")


# Formularios para usar la API desde el navegador (GET); el procesamiento está en las rutas POST
@app.route("/registro", methods=["GET"])
def pagina_registro():
    return pagina_formulario("Registro de usuario", "Registrarse", "/registro", "/login",
                             "/login", "Ya tengo cuenta: iniciar sesión")


@app.route("/login", methods=["GET"])
def pagina_login():
    return pagina_formulario("Iniciar sesión", "Ingresar", "/login", "/tareas",
                             "/registro", "Crear una cuenta")


# Endpoint de registro: guarda el usuario con la contraseña hasheada
@app.route("/registro", methods=["POST"])
def registro():
    usuario, contrasenia = leer_credenciales()
    if usuario is None:
        return jsonify(error='Se espera un JSON con "usuario" y "contraseña" no vacíos'), 400

    # Nunca se guarda la contraseña en texto plano: solo su hash (con sal incluida)
    password_hash = generate_password_hash(contrasenia)
    fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conexion = conectar_bd()
    try:
        with conexion:
            conexion.execute(
                "INSERT INTO usuarios (usuario, password_hash, fecha_registro) VALUES (?, ?, ?)",
                (usuario, password_hash, fecha)
            )
    except sqlite3.IntegrityError:
        # la columna usuario es UNIQUE: ya existe alguien con ese nombre
        return jsonify(error="El usuario ya existe"), 409
    except sqlite3.Error:
        return jsonify(error="Error del servidor al guardar el usuario"), 500
    finally:
        conexion.close()

    return jsonify(mensaje="Usuario registrado correctamente"), 201


# Endpoint de login: compara la contraseña recibida con el hash guardado
@app.route("/login", methods=["POST"])
def login():
    usuario, contrasenia = leer_credenciales()
    if usuario is None:
        return jsonify(error='Se espera un JSON con "usuario" y "contraseña" no vacíos'), 400

    conexion = conectar_bd()
    try:
        fila = conexion.execute(
            "SELECT password_hash FROM usuarios WHERE usuario = ?", (usuario,)
        ).fetchone()
    except sqlite3.Error:
        return jsonify(error="Error del servidor al consultar el usuario"), 500
    finally:
        conexion.close()

    # Mismo mensaje si falla el usuario o la contraseña, para no revelar cuál de los dos existe
    if fila is None or not check_password_hash(fila[0], contrasenia):
        return jsonify(error="Usuario o contraseña incorrectos"), 401

    # La sesión queda guardada en una cookie firmada; /tareas la usa para dar acceso
    session["usuario"] = usuario
    return jsonify(mensaje="Inicio de sesión exitoso"), 200


# Endpoint de tareas: devuelve el HTML de bienvenida solo si hay una sesión iniciada
@app.route("/tareas", methods=["GET"])
def tareas():
    usuario = session.get("usuario")
    if usuario is None:
        # Un navegador (su cabecera Accept nombra text/html) recibe una página con el enlace
        # al login; el resto de los clientes (curl, requests envían */*) reciben el error en JSON
        if "text/html" in request.headers.get("Accept", ""):
            return ACCESO_RESTRINGIDO, 401
        return jsonify(error="Acceso denegado: primero hay que iniciar sesión en /login"), 401

    # escape() evita que un nombre de usuario con HTML se interprete como código (XSS)
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>Gestión de Tareas</title>
</head>
<body>
    <h1>¡Bienvenido, {escape(usuario)}!</h1>
    <p>Iniciaste sesión correctamente en el Sistema de Gestión de Tareas.</p>
</body>
</html>"""


def puerto_disponible():
    # Prueba abrir el puerto antes de iniciar Flask. El servidor de desarrollo usa
    # SO_REUSEADDR, que en Windows permite que dos procesos escuchen el mismo puerto
    # sin error; por eso se verifica con un socket común (sin esa opción)
    prueba = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        prueba.bind((HOST, PORT))
        return True
    except OSError:
        return False
    finally:
        prueba.close()


if __name__ == "__main__":
    try:
        inicializar_bd()
    except sqlite3.Error as error:
        print(f"No se pudo acceder a la base de datos: {error}")
        raise SystemExit(1)

    if not puerto_disponible():
        print(f"No se pudo iniciar el servidor: el puerto {PORT} ya está en uso.")
    else:
        app.run(host=HOST, port=PORT)
