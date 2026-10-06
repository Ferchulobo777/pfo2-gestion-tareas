# PFO 2: Sistema de Gestión de Tareas con API y Base de Datos

Programación sobre Redes, Tecnicatura Superior en Desarrollo de Software (IFTS N° 29)

## Descripción

API REST desarrollada con Flask. Permite registrar usuarios, iniciar sesión y acceder a una página de bienvenida (`/tareas`) que solo se muestra a quien ya inició sesión. Los usuarios se guardan en SQLite y la contraseña se almacena como hash, nunca en texto plano. También incluye un cliente de consola que consume la API.

Documentación publicada con GitHub Pages: https://ferchulobo777.github.io/pfo2-gestion-tareas/ (se genera desde la carpeta `docs/`).

## Requisitos

- Python 3.9 o superior
- Flask (incluye `werkzeug`, que se usa para hashear las contraseñas)
- requests (solo lo usa el cliente de consola)

```
pip install -r requirements.txt
```

## Cómo ejecutar

1. Iniciar el servidor:

```
python servidor.py
```

Debe mostrar `Running on http://127.0.0.1:5000`. Al iniciar crea el archivo `usuarios.db` si todavía no existe.

2. En otra terminal, iniciar el cliente de consola:

```
python cliente.py
```

Opciones del menú: 1 registrarse, 2 iniciar sesión, 3 ver tareas, 4 salir.

## Endpoints

| Método | Ruta | Descripción | Respuestas |
|---|---|---|---|
| POST | `/registro` | Crea un usuario. Recibe `{"usuario": "nombre", "contraseña": "1234"}` | 201 creado, 400 datos inválidos, 409 usuario existente |
| POST | `/login` | Verifica las credenciales e inicia la sesión (cookie firmada) | 200 correcto, 400 datos inválidos, 401 credenciales incorrectas |
| GET | `/tareas` | Devuelve el HTML de bienvenida. Requiere sesión iniciada | 200 con HTML, 401 sin sesión |

## Cómo probarlo

### Con curl (en Windows se usa `curl.exe`)

```
curl.exe -i -X POST http://127.0.0.1:5000/registro -H "Content-Type: application/json" -d "{\"usuario\": \"fernando\", \"contraseña\": \"1234\"}"

curl.exe -i -c cookies.txt -X POST http://127.0.0.1:5000/login -H "Content-Type: application/json" -d "{\"usuario\": \"fernando\", \"contraseña\": \"1234\"}"

curl.exe -b cookies.txt http://127.0.0.1:5000/tareas
```

La opción `-c` guarda la cookie de sesión que devuelve el login y `-b` la envía en el pedido siguiente. Sin la cookie, `/tareas` responde 401.

### Casos que se verificaron

- Registro de un usuario nuevo: 201.
- Registro del mismo usuario por segunda vez: 409.
- Login con contraseña incorrecta: 401.
- `GET /tareas` sin haber iniciado sesión: 401.
- Login correcto y luego `GET /tareas`: 200 con la página de bienvenida.
- Contenido de la tabla `usuarios`, donde la contraseña figura como hash: `sqlite3 usuarios.db "SELECT usuario, password_hash FROM usuarios;"`

## Capturas de pantalla de las pruebas

| Archivo | Prueba |
|---|---|
| `docs/capturas/01-registro.png` | Registro de usuario (201) |
| `docs/capturas/02-login.png` | Inicio de sesión (200) |
| `docs/capturas/03-tareas.png` | Página de bienvenida en `/tareas` |
| `docs/capturas/04-hash-en-bd.png` | Contraseña almacenada como hash en SQLite |
| `docs/capturas/05-casos-error.png` | Respuestas 409 y 401 |
| `docs/capturas/06-cliente-consola.png` | Sesión completa con el cliente de consola |

## Estructura

- `servidor.py`: API Flask con SQLite (registro, login y tareas).
- `cliente.py`: cliente de consola que consume la API.
- `requirements.txt`: dependencias.
- `usuarios.db`: base SQLite. Se crea al iniciar el servidor y no se versiona.
- `docs/`: sitio publicado con GitHub Pages.

## Base de datos

Tabla `usuarios`:

| Campo | Tipo | Descripción |
|---|---|---|
| id | INTEGER | Clave primaria autoincremental |
| usuario | TEXT | Nombre de usuario (único) |
| password_hash | TEXT | Hash de la contraseña calculado con `werkzeug.security` |
| fecha_registro | TEXT | Fecha y hora del registro |

## Decisiones técnicas

- Hash de contraseñas: se usan `generate_password_hash` y `check_password_hash` de `werkzeug.security`. El hash incluye una sal aleatoria, por lo que dos usuarios con la misma contraseña tienen hashes distintos.
- Sesión: al iniciar sesión, Flask guarda el usuario en una cookie firmada con `secret_key`. La ruta `/tareas` consulta esa cookie para permitir o negar el acceso. La clave puede definirse con la variable de entorno `SECRET_KEY`; si no existe, se genera una aleatoria al iniciar el servidor.
- Login: si falla el usuario o la contraseña se devuelve el mismo mensaje, para no revelar qué usuarios existen.
- Seguridad de las consultas: las sentencias SQL son parametrizadas (`?`) para evitar inyección SQL, y el nombre de usuario se escapa al armar el HTML de `/tareas`.
- Puerto ocupado: antes de iniciar Flask se prueba abrir el puerto con un socket común. El servidor de desarrollo de Flask usa `SO_REUSEADDR`, que en Windows permite que dos procesos escuchen en el mismo puerto sin error.

## Respuestas conceptuales

### ¿Por qué hashear contraseñas?

Porque la base de datos puede filtrarse por una vulnerabilidad, un backup mal protegido o el acceso de una persona no autorizada. Si las contraseñas estuvieran en texto plano, quien obtenga la base tendría de inmediato las credenciales de todos los usuarios, y como muchas personas repiten la misma contraseña en varios servicios, también podría ingresar a esas otras cuentas.

Un hash es una función de un solo sentido: a partir de la contraseña se calcula el hash, pero no se puede recorrer el camino inverso. Para validar un login, el servidor calcula el hash de lo que escribió el usuario y lo compara con el hash guardado, sin necesidad de conocer ni almacenar la contraseña original.

Además, las librerías actuales agregan una sal aleatoria a cada contraseña, lo que evita que contraseñas iguales produzcan el mismo hash e inutiliza las tablas precalculadas (rainbow tables). También usan algoritmos lentos a propósito (scrypt, bcrypt, PBKDF2), que encarecen los ataques de fuerza bruta. El hash no impide que la base se filtre, pero reduce mucho el daño cuando eso ocurre.

### Ventajas de usar SQLite en este proyecto

- No necesita un servidor de base de datos: es una base embebida que se guarda en un único archivo.
- El módulo `sqlite3` viene incluido en Python, por lo que no se instala nada adicional.
- No requiere configuración: la base y la tabla se crean al iniciar el servidor, y cualquiera puede clonar el repositorio y probarlo.
- Es portable: todo está en un archivo que se copia, respalda o elimina fácilmente.
- Los datos persisten cuando se reinicia el servidor, a diferencia de guardarlos en memoria.
- Usa SQL estándar y soporta transacciones, lo que permite restricciones como `UNIQUE` sobre el usuario y consultas parametrizadas.
- Es suficiente para la escala del proyecto, con pocos usuarios y poca concurrencia. Si hubiera muchos usuarios escribiendo a la vez, convendría migrar a un motor cliente servidor como PostgreSQL o MySQL.
