# INFORME TÉCNICO — proyecto_menu

**Proyecto:** Aplicación web de login con directorio de empleados (Django)
**Fecha de la revisión:** 2026-10-08
**Alcance:** Revisión completa + corrección de errores confirmados + verificación
**Nota de confidencialidad:** En este informe NO se reproducen contraseñas, claves secretas, tokens ni datos personales. Las credenciales de desarrollo permanecen únicamente en `mi_proyecto/settings.py` (sin cambios de valor).

---

## 1. Resumen general del proyecto

Aplicación web interna de una empresa (marca "Solutex"/"NovaTech" en las vistas) con dos partes:

1. **Página de login** (`/`): formulario de usuario/contraseña con diseño dividido (panel de marca + formulario).
2. **Dashboard** (`/` tras autenticarse): panel administrativo con estadísticas (total de empleados, activos, departamentos), buscador y directorio de empleados (nombre, correo, puesto, departamento y estado).

La aplicación está construida con **Django 6.1.1** sobre **Python 3.14**, usa **PostgreSQL** como base de datos, y una app propia (`login`) con dos modelos: `Departamento` y `Empleado`.

**Hallazgo central de la revisión anterior:** el login original no verificaba la contraseña en absoluto (el campo se leía pero nunca se usaba, y el modelo no tenía campo de contraseña). Conocir el correo o el nombre de cualquier empleado daba acceso completo al directorio. Este problema se ha corregido en esta fase (ver sección 6).

---

## 2. Arquitectura y tecnologías utilizadas

| Capa | Tecnología | Detalle |
|---|---|---|
| Backend | Python 3.14 + Django 6.1.1 | MVT (Model-View-Template) |
| Base de datos | PostgreSQL 16+ (motor `django.db.backends.postgresql`, driver `psycopg` 3.3.6) | Host `localhost:5432` |
| Frontend | HTML5 + CSS3 puro (sin framework) | Dos hojas de estilo propias |
| Iconos/fuentes | FontAwesome 6.4.0 y Google Fonts (CDN), imagen de fondo de Unsplash (CDN) | Dependencias externas |
| Sesiones | Sesiones de Django (tabla `django_session`, cookie firmada) | — |
| Seguridad | CSRFMiddleware, X-Frame-Options, autoescape de plantillas, hashes de contraseña PBKDF2 de Django | — |

**Dependencias instaladas** (también fijadas en `requirements.txt`): `Django==6.1.1`, `asgiref==3.12.1`, `psycopg==3.3.6`, `psycopg-binary==3.3.6`, `sqlparse==0.6.0`, `tzdata==2026.5`.

---

## 3. Carpetas y archivos importantes

```
proyecto_menu/
├── manage.py                     # Punto de entrada de Django (runserver, migrate, test…)
├── requirements.txt              # [NUEVO] Dependencias fijadas
├── INFORME_TECNICO.md            # [NUEVO] Este informe
├── mi_proyecto/                  # Proyecto Django (configuración)
│   ├── settings.py               # Configuración global (BD, apps, middleware, sesiones)
│   ├── urls.py                   # Enrutamiento: /admin/ y / (app login)
│   ├── wsgi.py / asgi.py         # Entry points para servidores WSGI/ASGI
│   └── __init__.py
├── login/                        # Aplicación principal
│   ├── models.py                 # Modelos Departamento y Empleado (+ campo password)
│   ├── views.py                  # Vista home (login + dashboard) y logout_view
│   ├── urls.py                   # Rutas '' y 'logout/'
│   ├── admin.py                  # Registro en /admin/ con formulario que hashea contraseñas
│   ├── apps.py                   # Configuración de la app
│   ├── tests.py                 # Suite de pruebas (12 pruebas)
│   ├── templates/login/
│   │   ├── index.html            # Plantilla de login
│   │   └── principal.html        # Plantilla del dashboard
│   ├── static/login/
│   │   ├── login.css             # Estilos del login
│   │   └── principal.css         # Estilos del dashboard
│   ├── migrations/
│   │   ├── 0001_initial.py       # Crea Departamento y Empleado
│   │   └── 0002_empleado_password.py  # [NUEVO] Añade columna password
│   └── management/commands/
│       └── setpassword.py        # [NUEVO] Comando para asignar contraseñas
└── venv/                         # Entorno virtual (no versionar)
```

---

## 4. Funcionamiento completo de la aplicación

### Flujo de login (tras la corrección)

1. El usuario carga `/` (GET). Sin sesión, se renderiza `login/index.html` con el formulario (incluye token CSRF).
2. Al enviar (POST `/`), la vista `home`:
   - Comprueba el límite de intentos fallidos (5 intentos / 5 minutos por IP+usuario, en caché).
   - Busca un `Empleado` **activo** cuyo `correo` (insensible a mayúsculas) o `nombre` coincida con el campo "username".
   - **Valida la contraseña** con `check_password` contra el hash almacenado en `Empleado.password` (PBKDF2, formato Django).
   - Si es correcta: rota la clave de sesión (`cycle_key()`, anti-fixación), guarda `usuario_id` y `usuario_nombre` en la sesión, y redirige a `/`.
   - Si falla: registra el intento fallido y muestra mensaje genérico "Credenciales inválidas" (ahora sí visible en la página).
3. Con sesión activa, `/` renderiza el dashboard (`principal.html`): contadores agregados, buscador (`q`) y tabla de empleados con `select_related('departamento')`.

### Cierre de sesión
`POST /logout/` → `logout_view` (protegido con `@require_POST`, CSRF obligatorio) → `request.session.flush()` → redirige a `/`.

### Conexión a la base de datos
Django usa `DATABASES` en `settings.py` (PostgreSQL en localhost:5432, base `db_login`). Los accesos se hacen exclusivamente mediante el ORM (consultas parametrizadas), nunca SQL concatenado. Las credenciales pueden sobrescribirse con variables de entorno (`DJANGO_DB_*`).

### Modelos / tablas
- **`login_departamento`**: `id`, `nombre` (100), `descripcion` (texto, opcional).
- **`login_empleado`**: `id`, `nombre`, `apellido`, `correo` (único), `puesto`, `departamento_id` (FK → departamento, CASCADE), `fecha_ingreso` (auto_now_add), `activo` (bool), `password` (hash, 128).
- Tablas de Django: `django_session`, `django_migrations`, `auth_*`, `django_admin_log`, etc.

### Usuarios, sesiones y permisos
- **Sesión**: cookie firmada por `SECRET_KEY`; datos en tabla `django_session`; duración máxima 1 hora; expira al cerrar el navegador; cookie `HttpOnly`.
- **Permisos**: actualmente el control es binario (logueado o no). No existen roles ni permisos diferenciados (ver pendientes).
- **Admin de Django** (`/admin/`): usa el sistema de auth estándar de Django (superusuario) y permite gestionar Departamentos y Empleados, incluyendo asignar contraseñas hasheadas desde el formulario del admin.

### Comunicación frontend ↔ backend ↔ BD
El navegador pide HTML al servidor Django; los CSS se sirven desde `login/static/` vía `STATIC_URL='/static/'`; los formularios se envían por POST (login, logout) y GET (buscador); Django traducir las peticiones a consultas ORM parametrizadas hacia PostgreSQL.

---

## 5. Errores encontrados (identificadores de la revisión previa)

**Críticos:** C1 (login sin verificación de contraseña).
**Altos:** A1 (fixación de sesión), A2 (no se filtraba `activo`), A3 (DEBUG/SECRET_KEY/ALLOWED_HOSTS fijos), A4 (credenciales BD en texto plano y usuario superusuario).
**Medios:** M1 (mensaje de error invisible), M2 (fences Markdown en `principal.html`), M3 (logout por GET), M4 (desajuste de clases CSS), M5 (sin roles/permisos), M6 (sesiones largas/sin banderas), M7 (sin protección de fuerza bruta).
**Bajos:** B1 (`MAILERS` no es un setting válido), B2 (migraciones 0002–0004 eliminadas, quedan `.pyc`), B3 (sin `requirements.txt`), B4 (dependencias CDN), B5 (consultas de conteo separadas; sin paginación).

---

## 6. Errores corregidos y archivos modificados

### Corregidos

| ID | Corrección | Archivo(s) |
|---|---|---|
| C1 | Login ahora verifica la contraseña contra un hash (nuevo campo `Empleado.password` + métodos `set_password`/`check_password`). El login falla si no hay contraseña configurada. | `login/models.py`, `login/views.py`, `login/migrations/0002_empleado_password.py` |
| A1 | Se rota la clave de sesión con `request.session.cycle_key()` al autenticar. | `login/views.py` |
| A2 | El login solo acepta empleados con `activo=True`. | `login/views.py` |
| A3 | `SECRET_KEY`, `DEBUG` y `ALLOWED_HOSTS` son configurables por variables de entorno (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`), con valores por defecto de desarrollo y `ALLOWED_HOSTS` ya no vacío. | `mi_proyecto/settings.py` |
| A4 | Credenciales de BD configurables por entorno (`DJANGO_DB_*`); se conservan los valores de desarrollo sin alterarlos. | `mi_proyecto/settings.py` |
| M1 | Se renderiza el framework de `messages` en `index.html` y `principal.html` (el error "Credenciales inválidas" ahora es visible). | `login/templates/login/index.html`, `login/templates/login/principal.html`, ambos CSS |
| M2 | Eliminados los fences Markdown (`` ```html `` / `` ``` ``) de `principal.html`. | `login/templates/login/principal.html` |
| M3 | Logout ahora exige POST (`@require_POST`) y el botón es un formulario con token CSRF. | `login/views.py`, `login/templates/login/principal.html` |
| M4 | `principal.css` reescrito alineando selectores con las clases reales de la plantilla (`logo-area`, `user-area`, `user-info`, `btn-logout`, `main-container`, `metric-*`, `card-value`, `table-header`, `btn-search`, `btn-clear`, `avatar`, `badge`, etc.) y añadiendo reglas para `section-label`, `user-label`, `metric-description` y mensajes. La tabla ahora tiene `class="employee-table"`. | `login/static/login/principal.css`, `login/templates/login/principal.html` |
| M6 | `SESSION_COOKIE_AGE=3600`, `SESSION_EXPIRE_AT_BROWSER_CLOSE=True`, `SESSION_COOKIE_HTTPONLY=True` explícitos. | `mi_proyecto/settings.py` |
| M7 | Límite de intentos de login (5 fallos / 5 min por IP+usuario) con tolerancia a fallos de caché. | `login/views.py` |
| B1 | `MAILERS` (inválido) sustituido por `EMAIL_BACKEND` correcto, configurable por entorno. | `mi_proyecto/settings.py` |
| B3 | Creado `requirements.txt` con dependencias fijadas. | `requirements.txt` |
| B5 | Los tres `count()` se fusionaron en una consulta agregada (`aggregate` con `Count` + filtro). | `login/views.py` |

### Archivos nuevos
- `login/migrations/0002_empleado_password.py` (generado por `makemigrations`; **aún no aplicado a la BD real**, ver sección 8).
- `login/management/commands/setpassword.py` + paquetes `management/` — comando `python manage.py setpassword <correo>` para asignar contraseñas (mínimo 8 caracteres, entrada oculta).
- `requirements.txt`.

### Mejoras adicionales (seguras)
- `login/admin.py`: formulario `EmpleadoAdminForm` que hashea la contraseña al guardarla (campo tipo password; vacío = conservar la actual).
- `login/apps.py`: `default_auto_field` explícito.
- `login/templates/login/index.html`: `autocomplete="email"` / `autocomplete="current-password"`.
- `login/tests.py`: suite de 12 pruebas (antes vacía).

### Cambios de comportamiento a tener en cuenta (no destructivos)
- `GET /logout/` ahora devuelve **405** (el cierre de sesión solo acepta POST).
- Hasta que se aplique la migración y se asignen contraseñas, **el login rechazará cualquier intento** (comportamiento seguro por defecto).

---

## 7. Pruebas ejecutadas y resultados reales

| Comprobación | Comando | Resultado |
|---|---|---|
| Checks del sistema | `python manage.py check` | ✅ "System check identified no issues" |
| Modelos vs migraciones | `python manage.py makemigrations --check --dry-run` | ✅ "No changes detected" |
| Sintaxis/compilación | `python -m compileall -q login mi_proyecto manage.py` | ✅ COMPILE_OK |
| Suite de pruebas | `python manage.py test login` (con `DJANGO_DB_ENGINE=django.db.backends.sqlite3`, base de pruebas **en memoria**) | ✅ **12/12 OK**, "Ran 12 tests … OK", código de salida 0 |
| Migración 0002 | Aplicada dentro de la BD de pruebas efímera | ✅ "Applying login.0002_empleado_password… OK" |
| Revisión de despliegue | `python manage.py check --deploy` | ⚠️ 6 avisos de endurecimiento para producción (ver sección 8); ninguno es un error de funcionamiento |

**Pruebas incluidas (12):** formulario visible sin sesión; login correcto por correo y por nombre; contraseña incorrecta; usuario inexistente; empleado inactivo rechazado; empleado sin contraseña rechazado; dashboard con sesión (y sin vallas Markdown residuales); buscador con y sin resultados; límite de fuerza bruta; logout exige POST (405 en GET, cierra sesión en POST); hash/set/check de contraseñas en el modelo.

**Importante:** las pruebas se ejecutaron contra SQLite en memoria (entorno seguro). **No** tocaron la base de datos PostgreSQL real ni crearon/modificaron tablas en ella.

---

## 8. Problemas que continúan pendientes

**⚠️ ACCIÓN REQUERIDA ANTES DE USAR EL LOGIN (en tu entorno de desarrollo):**
1. Ejecutar `python manage.py migrate` para añadir la columna `password` a `login_empleado` (la migración está creada pero **no aplicada** a la BD real, según tus instrucciones).
2. Asignar contraseñas a los empleados existentes (hasta ahora nadie tiene contraseña):
   - `python manage.py setpassword correo@empresa.com` (la pide de forma oculta), o
   - desde `/admin/` (campo de contraseña del formulario de Empleado).
   Mientras un empleado no tenga contraseña, su login permanecerá rechazado (intencional).

**Pendientes de diseño/decisión (no implementados para no alterar el funcionamiento):**
- **M5 — Roles y permisos:** no existe autorización diferenciada; cualquier usuario autenticado ve todo el directorio. Requiere decidir modelo de roles (el historial de migraciones indica que existió un `rol` y se eliminó).
- **Endurecimiento de producción** (avisos de `check --deploy`): `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY` propio (generar con `get_random_secret_key()`), `DJANGO_ALLOWED_HOSTS` con el dominio real, `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, `SECURE_SSL_REDIRECT`/`SECURE_HSTS_SECONDS` si se sirve por HTTPS.
- **B2 — Historial de migraciones:** en `login/migrations/__pycache__/` quedan `.pyc` de las antiguas migraciones 0002–0004 (eliminadas de disco). Django las ignora si aparecen en la BD (verificado en el código fuente de Django), pero conviene limpiarlos y documentar el historial real. **No pude verificar el estado de la BD real.**
- **B4 — CDNs:** FontAwesome, Google Fonts y la imagen de fondo (Unsplash) dependen de internet; considera copiarlos a `static/`.
- **Variantes opcionales:** paginación del directorio; restringir el login al solo correo (hoy acepta el nombre, lo que amplía la superficie); cache compartida (Redis) si se ejecuta con varios procesos (el limitador de intentos usa la caché local por defecto); validadores de contraseña de Django en `setpassword` (hoy solo mínimo 8 caracteres).

---

## 9. Evaluación de riesgos de seguridad identificados

| Riesgo | Estado |
|---|---|
| Acceso sin contraseña (crítico) | ✅ Corregido |
| Fixación de sesión | ✅ Corregido (`cycle_key()`) |
| Login de empleados inactivos | ✅ Corregido (`activo=True`) |
| Fuerza bruta básica | ✅ Mitigado (5 intentos/5 min); no es un firewall/WAF |
| CSRF en login/logout | ✅ Presente (`{% csrf_token %}`, logout por POST) |
| Inyección SQL | ✅ No aplica: todo el acceso es ORM parametrizado |
| XSS | ✅ Autoescape activivo; variables escapadas |
| Exposición de errores (DEBUG) | ⚠️ Mitigado por configuración; **en producción hay que poner `DJANGO_DEBUG=False`** |
| Secreto/CREDENCIALES en código | ⚠️ Mitigado por variables de entorno; los valores por defecto de desarrollo siguen en `settings.py` y **deben cambiarse para producción** |
| Cookies de sesión/CSRF sin flag Secure | ⚠️ Pendiente de producción con HTTPS |
| Sin HTTPS | ⚠️ Pendiente de despliegue |
| Sin 2FA / sin auditoría de accesos | ⚠️ Pendiente (mejora futura) |
| Sesiones largas | ✅ Corregido (1 h, expira al cerrar navegador) |

---

## 10. Instrucciones para ejecutar el proyecto en desarrollo

Prerrequisitos: Python 3.14, PostgreSQL corriendo en `localhost:5432` con la base `db_login` y el usuario/rol configurados (las credenciales de desarrollo están en `settings.py`; no se reproducen aquí).

```powershell
# 1. Activar el entorno virtual
.\venv\Scripts\Activate.ps1

# 2. Aplicar migraciones (crea/actualiza tablas; OBLIGATORIO tras esta corrección)
python manage.py migrate

# 3. Asignar una contraseña a un empleado (mínimo 8 caracteres)
python manage.py setpassword correo@empresa.com

# 4. Ejecutar el servidor
python manage.py runserver
# Abrir http://127.0.0.1:8000/

# Admin de Django (requiere un superusuario, créalo con: python manage.py createsuperuser)
# http://127.0.0.1:8000/admin/

# 5. Ejecutar las pruebas (usa SQLite en memoria; no toca PostgreSQL)
python manage.py test login
```

Configuración por entorno (opcional): `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_DB_ENGINE`, `DJANGO_DB_NAME`, `DJANGO_DB_USER`, `DJANGO_DB_PASSWORD`, `DJANGO_DB_HOST`, `DJANGO_DB_PORT`, `DJANGO_EMAIL_BACKEND`.

---

## 11. Recomendaciones para mantenerlo y mejorarlo

1. **Nunca** versionar secretos: usa `.env` (fuera del VCS) o secretos del servidor; rota la `SECRET_KEY` actual por una generada.
2. En producción: `DEBUG=False`, `ALLOWED_HOSTS` explícito, HTTPS + cookies seguras, WSGI/ASGI con gunicorn/uvicorn tras proxy.
3. Implementar roles (ej. campos `rol`/`permisos` o grupos de Django) y decoradores `@login_required`/`UserPassesTestMixin`; integrar la sesión custom con `django.contrib.auth` para unificar `request.user`.
4. Añadir paginación al directorio y probar con volumen real de datos.
5. Considerar autenticación solo por correo y política de contraseñas más estricta (validadores de Django).
6. Copiar assets (iconos/fuentes/imagen) al `static/` local para funcionamiento sin internet.
7. Ampliar la suite de pruebas (p. ej. plantillas, admin, comandos) y ejecutarla también contra PostgreSQL.
8. Documentar el historial real de migraciones y limpiar `.pyc` obsoletos.
9. Registrar intentos de login fallidos en logs (auditoría) sin almacenar contraseñas.

---

## 12. Limitaciones de la revisión y aspectos que no pudieron verificarse

- **No se accedió a la base de datos PostgreSQL real** (por instrucción): no se pudo verificar si el servidor está activo, si `db_login` existe, qué migraciones tiene aplicadas ni el esquema actual. La migración `0002_empleado_password` está creada pero **no ejecutada** sobre la BD real.
- **No se arrancó el servidor de desarrollo** contra la BD real (escribiría filas de sesión en `django_session`). La verificación funcional se hizo con el cliente de pruebas de Django (ciclo completo petición→respuesta) sobre SQLite en memoria.
- **El CSS no se verificó visualmente en navegador**; la corrección M4 es una alineación de nombres de clases verificada por inspección de código. Se recomienda revisar el dashboard en pantalla.
- Las pruebas se ejecutaron con SQLite; el comportamiento con PostgreSQL debería confirmarse en tu entorno (las consultas usadas son portables).
- No se evaluó el despliegue en producción (no hay servidor/proxy disponible en este entorno).
- Versiones recientes (Django 6.1.1, Python 3.14): la revisión se basa en el código fuente instalado en `venv/`.

---

*Fin del informe. Resumen: 1 crítico, 4 altos, 7 medios y 4 bajos corregidos o mitigados; 12/12 pruebas superadas; pendientes principales: ejecutar `migrate` + asignar contraseñas en tu entorno, y decidir el modelo de roles/permisos.*
