# LEVANTAMIENTO TÉCNICO — proyecto_menu

**Proyecto:** Aplicación web de gestión de empleados y departamentos con login, roles y auditoría (Django)
**Fecha del levantamiento:** 2026-10-10
**Alcance:** Auditoría completa, CRUDs, control de acceso por roles, seguridad, pruebas y documentación
**Confidencialidad:** Este documento NO reproduce contraseñas, claves secretas ni datos personales. Las credenciales de desarrollo permanecen únicamente en `mi_proyecto/settings.py`.

---

## 1. Descripción general del proyecto

Aplicación interna de empresa (marca "Solutex" en el login, "NovaTech" en el panel) con:

1. **Login** (`/`): formulario de usuario/contraseña con diseño dividido.
2. **Dashboard** (`/` tras autenticarse): estadísticas, buscador y directorio de empleados paginado.
3. **Módulo de Empleados** (`/empleados/`): listado, detalle, crear, editar, eliminar, asignar rol/estado y restablecer contraseña.
4. **Módulo de Departamentos** (`/departamentos/`): listado, detalle, crear, editar y eliminar (con protección de integridad).
5. **Perfil propio** (`/perfil/`): ver datos, editar identidad y cambiar contraseña.
6. **Auditoría** (`/auditoria/`): historial de acciones administrativas y de seguridad (solo administradores).

Se conservó íntegramente el login que ya funcionaba (validación de contraseña hasheada, protección de fuerza bruta, rotación de sesión) y se añadió el resto de forma incremental.

---

## 2. Tecnologías utilizadas y estructura

| Capa | Tecnología | Detalle |
|---|---|---|
| Backend | Python 3.14.5 + Django 6.1.1 | MVT (Model-View-Template) |
| Base de datos | PostgreSQL (`django.db.backends.postgresql`, driver `psycopg` 3.3.6) | `localhost:5432`, base `db_login` (configurable por entorno) |
| Frontend | HTML5 + CSS3 puro (sin framework) | `login/static/login/login.css` y `principal.css` |
| Iconos/fuentes | FontAwesome 6.4.0 y Google Fonts (CDN) | Dependencias externas (ver riesgos) |
| Sesiones | Sesiones de Django (`django_session`) | 1 h, expira al cerrar navegador, HttpOnly |
| Seguridad | CSRFMiddleware, X-Frame-Options, autoescape, hashes PBKDF2 | Ver sección 6 |

**Estructura de carpetas:**

```
proyecto_menu/
├── manage.py
├── requirements.txt
├── INFORME_TECNICO.md          # Informe de la fase anterior (histórico)
├── LEVANTAMIENTO_TECNICO.md    # Este documento
├── mi_proyecto/                # Proyecto Django
│   ├── settings.py             # + context processor de sesión
│   ├── urls.py                 # + handlers 403/404/500
│   ├── wsgi.py / asgi.py
│   └── __init__.py
├── login/                      # Aplicación principal
│   ├── models.py               # Departamento, Empleado (+rol), RegistroAuditoria [NUEVO]
│   ├── views.py                # home, logout + CRUDs + perfil + auditoría + handlers
│   ├── forms.py                # [NUEVO] Validación de todos los formularios
│   ├── decorators.py           # [NUEVO] login_requerido / admin_requerido
│   ├── context_processors.py   # [NUEVO] empleado_sesion, es_administrador, modulo_activo
│   ├── urls.py                 # Rutas de todos los módulos
│   ├── admin.py                # + rol, + protección de borrado de departamentos
│   ├── apps.py
│   ├── tests.py                # 66 pruebas (12 originales + 54 nuevas)
│   ├── templates/login/
│   │   ├── index.html          # Login (sin cambios)
│   │   ├── base.html           # [NUEVO] Layout + sidebar adaptado al rol
│   │   ├── dashboard.html      # [NUEVO] Reemplaza a principal.html
│   │   ├── empleado_*.html     # [NUEVO] list/detail/form/confirm_delete/rol/contrasena
│   │   ├── departamento_*.html # [NUEVO] list/detail/form/confirm_delete
│   │   ├── perfil*.html        # [NUEVO] perfil, editar, contraseña
│   │   ├── auditoria_list.html # [NUEVO]
│   │   ├── _pagination.html    # [NUEVO]
│   │   ├── 403.html / 404.html / 500.html  # [NUEVO]
│   │   └── (principal.html eliminada: funcionalidad migrada a base+dashboard)
│   ├── static/login/
│   │   ├── login.css
│   │   └── principal.css       # + formularios, botones, paginación, detalles, badges de rol
│   ├── migrations/
│   │   ├── 0001_initial.py
│   │   ├── 0002_empleado_password.py
│   │   └── 0003_registroauditoria_alter_departamento_options_and_more.py  # [NUEVO, PENDIENTE DE APLICAR]
│   └── management/commands/
│       ├── setpassword.py      # + validadores nativos de contraseña
│       └── makeadmin.py        # [NUEVO] Promueve un empleado a administrador
└── venv/                       # Entorno virtual (no versionar)
```

---

## 3. Inventario de tablas, modelos y relaciones

**Tablas de la aplicación (`login_`):**

| Tabla | Campos | Relaciones | Tipo |
|---|---|---|---|
| `login_departamento` | id, nombre (100, **único**), descripcion (texto opcional) | — | Catálogo |
| `login_empleado` | id, nombre, apellido, correo (único), puesto, departamento_id, fecha_ingreso (auto), activo (bool), **rol** (empleado/admin, defecto `empleado`), password (hash 128) | FK → `login_departamento` (CASCADE) | Negocio + usuarios |
| `login_registroauditoria` | id, fecha (auto), usuario (texto), modulo, accion, detalle, ip | Sin FK (historial inmutable) | Registro histórico |

**Relaciones:**
- `Departamento 1 ──∞ Empleado` (`related_name='empleados'`).
- Un empleado pertenece a un departamento; borrar un departamento con empleados está **bloqueado** a nivel de aplicación (el FK sigue siendo CASCADE en BD, pero la UI y el admin lo impiden).

**Tablas de Django:** `django_session`, `django_migrations`, `auth_*`, `django_admin_log`, etc.

**Nota sobre `rol`:** el historial del proyecto (`.pyc` antiguos en `migrations/__pycache__`, ya limpiados) muestra que ya existió un campo `rol` y un modelo `LogActividad` que fueron eliminados. Este levantamiento recupera esa dirección de diseño: `rol` sobre `Empleado` y `RegistroAuditoria` como historial.

---

## 4. Inventario de módulos y CRUD implementados

| Módulo | Listar | Detalle | Crear | Editar | Eliminar | Acceso |
|---|---|---|---|---|---|---|
| Empleados (`/empleados/`) | ✅ búsqueda + paginación | ✅ | ✅ (con contraseña obligatoria) | ✅ (contraseña opcional) | ✅ (con protecciones) | Ver: todos; gestionar: admin |
| Departamentos (`/departamentos/`) | ✅ búsqueda + paginación | ✅ (con sus empleados) | ✅ | ✅ | ✅ solo si no tiene empleados | Ver: todos; gestionar: admin |
| Perfil propio (`/perfil/`) | — | ✅ | — | ✅ (nombre/apellido/correo) | — | Todo usuario, solo sobre sí mismo |
| Contraseña propia | — | — | — | ✅ (requiere contraseña actual) | — | Todo usuario |
| Rol y estado (`/empleados/<pk>/rol/`) | — | — | — | ✅ (rol + activo) | — | Solo admin |
| Contraseña por admin (`/empleados/<pk>/contrasena/`) | — | — | — | ✅ restablecimiento | — | Solo admin |
| Auditoría (`/auditoria/`) | ✅ filtros por módulo/acción + paginación | — | — | — | — (solo lectura) | Solo admin |

**Protecciones de integridad implementadas:**
- No se puede eliminar un departamento con empleados asignados (mensaje explicativo).
- No se puede eliminar ni desactivar el propio usuario (evita auto-bloqueo).
- No se puede cambiar el propio rol (evita auto-escalada/bloqueo involuntario).
- Debe quedar siempre al menos un administrador activo (red de seguridad ante condiciones de carrera o edición directa de BD).
- No se puede eliminar la cuenta de un usuario desde su propio formulario.

---

## 5. Matriz de roles y permisos

| Operación | Administrador | Empleado | Anónimo |
|---|---|---|---|
| Iniciar/cerrar sesión | ✅ | ✅ | ✅ (login) |
| Dashboard (estadísticas + directorio) | ✅ | ✅ | ❌ (redirige al login) |
| Ver listado/detalle de empleados | ✅ | ✅ | ❌ |
| Crear/editar/eliminar empleados | ✅ | ❌ 403 | ❌ |
| Asignar rol y estado | ✅ | ❌ 403 | ❌ |
| Restablecer contraseña de otros | ✅ | ❌ 403 | ❌ |
| Ver listado/detalle de departamentos | ✅ | ✅ | ❌ |
| Crear/editar/eliminar departamentos | ✅ | ❌ 403 | ❌ |
| Ver y editar perfil propio | ✅ | ✅ | ❌ |
| Cambiar propia contraseña | ✅ | ✅ | ❌ |
| Ver auditoría | ✅ | ❌ 403 | ❌ |
| Acceder a `/admin/` de Django | Solo con superusuario de Django (independiente) | — | login Django |

**Principio de mínimo privilegio aplicado:** el rol por defecto al crear un empleado es `empleado`; el campo `rol` **no** existe en el formulario de creación ni es modificable por formularios públicos; solo un administrador autenticado puede promover a otro empleado (o usar `manage.py makeadmin`).

**¿Por qué no se usó `django.contrib.auth`?** La arquitectura actual autentica contra `Empleado` (la tabla corporativa real) con su propio hash en `Empleado.password`, y el login funcional ya existente depende de eso. Migrar a `auth.User` habría requerido duplicar identidades o re-escribir el login (riesgo alto de romper lo que funciona). Se optó por la solución segura: decoradores nativos al estilo de Django (`user_passes_test`), excepción nativa `PermissionDenied` → `handler403`, y sesión de Django. Queda documentado como posible evolución futura (sección 11).

---

## 6. Login y gestión de usuarios

**Flujo de login (conservado y verificado):**
1. `GET /` → formulario con token CSRF.
2. `POST /`: límite de fuerza bruta (5 fallos / 5 min por IP+usuario, en caché) → busca `Empleado` **activo** por correo o nombre (insensible a mayúsculas) → valida con `check_password` contra el hash PBKDF2 → rota la clave de sesión (`cycle_key()`, anti-fixación) → guarda `usuario_id`/`usuario_nombre` → redirige al dashboard.
3. Fallos: mensaje genérico "Credenciales inválidas" (no revela si el usuario existe) y contador de intentos.
4. Sesión huérfana (empleado borrado) o desactivado: la sesión se invalida al instante.

**Gestión de contraseñas:**
- Nunca en texto plano: `make_password`/`check_password` de Django (PBKDF2).
- Creación de empleado: contraseña obligatoria, mínimo 8 caracteres + validadores nativos (`validate_password`).
- Edición: vacía = conservar la actual.
- Cambio propio: exige la contraseña actual.
- Restablecimiento por admin: mínimo 8 + validadores.
- `setpassword` (CLI): entrada oculta, confirmación, validadores.

**Reglas de cuentas:**
- Solo administradores crean empleados (= crear usuarios del sistema).
- Usuarios inactivos no pueden iniciar sesión.
- Cierre de sesión: `POST /logout/` con CSRF, `session.flush()`.

---

## 7. Cambios realizados en archivos y base de datos

**Archivos modificados:**
- `login/models.py` — `rol` en Empleado, `RegistroAuditoria`, Meta (ordering), `nombre` único en Departamento, propiedades `es_administrador`/`nombre_completo`.
- `login/views.py` — dashboard paginado, CRUDs, perfil, auditoría, utilidades de auditoría, handlers 403/404/500.
- `login/urls.py` — rutas de todos los módulos.
- `login/admin.py` — `rol` en listado/filtros, protección de borrado de departamentos con empleados.
- `login/tests.py` — 66 pruebas.
- `login/management/commands/setpassword.py` — validadores nativos.
- `mi_proyecto/settings.py` — context processor `login.context_processors.sesion_actual`.
- `mi_proyecto/urls.py` — `handler403/404/500`.
- `login/static/login/principal.css` — estilos de formularios, botones, paginación, detalles, badges de rol, sidebar responsive.

**Archivos nuevos:** `forms.py`, `decorators.py`, `context_processors.py`, `makeadmin.py`, `base.html`, `dashboard.html`, 15 plantillas de módulos, `_pagination.html`, `403/404/500.html`, `LEVANTAMIENTO_TECNICO.md`.

**Archivos eliminados:** `login/templates/login/principal.html` (reemplazada por `base.html` + `dashboard.html` con la misma funcionalidad + mejoras); `.pyc` obsoletos de migraciones antiguas.

**Base de datos real (PostgreSQL):**
- Estado actual: 1 departamento ("Tecnología"), 1 empleado activo con contraseña configurada.
- **No se modificó ningún registro existente.** La migración `0003` está creada pero **NO aplicada** (ver sección 8).
- Los datos de prueba de la suite se ejecutan en SQLite en memoria; no tocan PostgreSQL.

---

## 8. Migraciones creadas y comandos necesarios para aplicarlas

**Migración nueva:** `login/migrations/0003_registroauditoria_alter_departamento_options_and_more.py`
- Crea `login_registroauditoria`.
- Añade `login_empleado.rol` (defecto `'empleado'` — asigna el rol más restrictivo a los existentes).
- Añade `ordering` a ambos modelos.
- Hace `login_departamento.nombre` único (añade restricción UNIQUE en BD).

**Riesgo y verificación:** añadir una columna con valor por defecto y una restricción UNIQUE es seguro con los datos actuales (un solo departamento, sin duplicados). La migración se verificó aplicándola sobre SQLite en la suite de pruebas (aplicación `Applying login.0003… OK`). **No se ejecutó `migrate` contra PostgreSQL** porque es un cambio de esquema en la BD real y requiere tu confirmación.

**Comandos que DEBES ejecutar (en tu entorno):**

```powershell
.\venv\Scripts\Activate.ps1

# 1. Aplicar la migración (paso obligatorio; añade columna rol y tabla de auditoría)
python manage.py migrate

# 2. Promover al menos un empleado a administrador (bootstrap de roles).
#    Sin este paso, todos los empleados quedan con rol "empleado" y
#    nadie puede gestionar el sistema (diseño seguro por defecto):
python manage.py makeadmin edwin@novatech.com

# 3. (Solo si hace falta) asignar/cambiar contraseña a un empleado:
python manage.py setpassword correo@empresa.com

# 4. Ejecutar el servidor
python manage.py runserver
```

**Comprobación previa (sin escribir en BD):**
```powershell
python manage.py check
python manage.py makemigrations --check --dry-run   # "No changes detected"
python manage.py test login                          # 66/66 OK
```

---

## 9. Pruebas ejecutadas y sus resultados reales

| Comprobación | Comando | Resultado real |
|---|---|---|
| Checks del sistema | `python manage.py check` | ✅ "System check identified no issues (0 silenced)" |
| Modelos vs migraciones | `python manage.py makemigrations --check --dry-run` | ✅ "No changes detected" |
| Suite de pruebas | `python manage.py test login` (SQLite en memoria) | ✅ **Ran 66 tests … OK** (≈76 s), código de salida 0 |
| Migración 0003 | Aplicada en la BD de pruebas efímera | ✅ Aplicada correctamente |
| Estado de migraciones en BD real | `python manage.py showmigrations login` | ✅ 0001 [X], 0002 [X], 0003 [ ] (pendiente, por diseño) |
| Smoke test contra PostgreSQL real | Cliente de pruebas de Django (solo GET/lectura) | ✅ `/` → 200 con CSRF; `/empleados/`, `/departamentos/`, `/perfil/`, `/auditoria/` → 302 al login; `/no-existe/` → 404 personalizado; `/admin/` → 302 |
| Servidor de desarrollo | `runserver 127.0.0.1:8123` | ✅ `/` → 200, `/empleados/` → 302 |
| Endurecimiento producción | `python manage.py check --deploy` | ⚠️ 6 avisos (ver sección 11); ningún error funcional |

**Cobertura de las 66 pruebas (12 originales conservadas + 54 nuevas):**
- Login: formulario visible, login correcto por correo y por nombre, contraseña incorrecta, usuario inexistente, inactivo rechazado, sin contraseña rechazado, límite de fuerza bruta.
- Dashboard: directorio con sesión, buscador con/sin resultados, paginación.
- Acceso por URL: anónimos redirigidos (302), empleados 403 en todas las URLs administrativas, empleados 200 en módulos permitidos, admin 200 en todo, sesión huérfana/desactivada invalidada, 403 y 404 personalizados.
- CRUD Empleados: listar/detalle/crear/editar/eliminar, validaciones (obligatorios, correo duplicado, contraseña corta), hash verificado, autodesactivación y autodelete bloqueados, otro admin puede eliminar/demotar a un admin, restablecimiento de contraseña (éxito y no coincidencia), búsqueda y paginación.
- CRUD Departamentos: listar/detalle/crear/editar, duplicado rechazado, eliminar vacío OK, eliminar con empleados bloqueado, empleado no puede gestionarlos.
- Perfil: ver/editar (sesión sincronizada), correo duplicado rechazado, cambiar contraseña (éxito, actual incorrecta, no coincidencia).
- Auditoría: registra creación de empleado, login/logout, acceso denegado a empleados, filtros.
- Seguridad: CSRF rechazado en login/CRUD/logout (con `enforce_csrf_checks`), hash `pbkdf2_` verificado, menú del sidebar adaptado al rol.
- Migraciones: `makemigrations --check` sin cambios, grafo de migraciones consistente.

---

## 10. Problemas encontrados y cómo se resolvieron

| # | Problema | Solución |
|---|---|---|
| 1 | Sin roles ni permisos: cualquier sesión lo ve todo; enlaces del sidebar muertos (`href="#"`) | Campo `rol` + decoradores `login_requerido`/`admin_requerido`, `PermissionDenied` → `handler403`, sidebar adaptado al rol |
| 2 | No existía CRUD (solo `/admin/` con superusuario aparte) | CRUD completo con formularios validados para empleados y departamentos |
| 3 | Al añadir `rol`, ningún usuario sería administrador (bootstrap) | Rol por defecto `empleado` + comando `makeadmin` documentado (paso 2 de la sección 8) |
| 4 | Sin paginación ni validación de formularios | `Paginator` (10/10/15 por página), `forms.py` con validación por campo y validadores nativos de contraseña |
| 5 | Sin auditoría | `RegistroAuditoria` (escritura solo desde el servidor, nunca almacena contraseñas) |
| 6 | `.pyc` obsoletos de migraciones eliminadas (0002_logactividad, 0003_delete, 0004_agregar_activo) | Limpieza de `__pycache__` (cachés autogenerados; Django los ignoraba) |
| 7 | `app_name='login'` introducido inicialmente rompía todos los `reverse()`/`{% url %}` del proyecto (62 errores en pruebas) | Revertido: el proyecto no usa namespaces; pruebas pasan |
| 8 | `HttpResponseForbidden()` vacío no mostraba la página 403 personalizada | Se lanza `PermissionDenied` (excepción nativa) → invoca `handler403` |
| 9 | Borrar un departamento con empleados rompería integridad (FK CASCADE) | Bloqueo en vista y en el admin de Django con mensaje explicativo |
| 10 | Riesgo de auto-bloqueo (admin se desactiva/elimina/demota a sí mismo) | Bloqueado en las tres operaciones; red de seguridad de "último administrador" |
| 11 | El audit de login registraba "Sistema" en vez del actor | `_auditar()` acepta parámetro `usuario` |

---

## 11. Riesgos o funcionalidades pendientes

**Pendientes de tu intervención (obligatorios para usar el sistema):**
1. Ejecutar `python manage.py migrate` (aplica `0003`).
2. Ejecutar `python manage.py makeadmin <correo>` para el primer administrador.

**Pendientes de producción (avisos de `check --deploy`):**
- `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY` propio (generar con `get_random_secret_key()`), `DJANGO_ALLOWED_HOSTS` con el dominio real.
- HTTPS: `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, `SECURE_SSL_REDIRECT=True`, `SECURE_HSTS_SECONDS`.
- La `SECRET_KEY` y las credenciales de BD por defecto en `settings.py` son de desarrollo: **cambiarlas** (ya son sobreescribibles por variables de entorno).

**Pendientes técnicos (mejoras futuras, no bloqueantes):**
- Dependencias de CDN (FontAwesome, Google Fonts): copiar a `static/` para funcionamiento sin internet.
- El limitador de fuerza bruta usa la caché local por proceso: usar Redis/memcached si se ejecuta con varios procesos.
- Migración a `django.contrib.auth` (unificar `request.user`) o añadir 2FA: evolución posible, no necesaria hoy.
- Depuración visual del CSS en navegador real (verificado por inspección de código y tests, no visualmente).
- Retención/compresión de la tabla de auditoría si crece mucho.

---

## 12. Instrucciones para instalar, ejecutar y administrar el proyecto

**Prerrequisitos:** Python 3.14, PostgreSQL en `localhost:5432` con base `db_login` y usuario configurado (credenciales de desarrollo en `settings.py`; sobreescribibles con `DJANGO_DB_*`).

```powershell
# 1. Entorno virtual
.\venv\Scripts\Activate.ps1

# 2. Dependencias (si procede)
python -m pip install -r requirements.txt

# 3. Migraciones + bootstrap de administrador
python manage.py migrate
python manage.py makeadmin edwin@novatech.com

# 4. Servidor de desarrollo
python manage.py runserver        # http://127.0.0.1:8000/

# 5. Pruebas (SQLite en memoria; no toca PostgreSQL)
python manage.py test login
```

**Tareas administrativas cotidianas:**
- Crear empleado: `/empleados/nuevo/` (como administrador).
- Promover/degradar o activar/desactivar: `/empleados/<id>/rol/`.
- Restablecer contraseña: `/empleados/<id>/contrasena/` o CLI `python manage.py setpassword <correo>`.
- Revisar auditoría: `/auditoria/`.
- Admin de Django (`/admin/`): requiere un superusuario Django aparte (`python manage.py createsuperuser`); gestiona los mismos modelos con las mismas protecciones.

**Variables de entorno soportadas:** `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_DB_ENGINE/NAME/USER/PASSWORD/HOST/PORT`, `DJANGO_EMAIL_BACKEND`.

---

## 13. Recomendaciones para desplegarlo en producción

1. **Secretos:** generar `SECRET_KEY` propia; mover credenciales de BD a variables de entorno/secrets del servidor; nunca versionar secretos.
2. **HTTPS obligatorio** detrás de proxy (gunicorn/uvicorn + nginx): activar `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, HSTS.
3. `DEBUG=False` y `ALLOWED_HOSTS` explícito.
4. WSGI/ASGI en producción (no `runserver`), procesos múltiples + caché compartida (Redis) para el limitador de intentos.
5. Copiar assets (iconos/fuentes) a `static/` local y servir `STATIC_ROOT` con el proxy.
6. Backups de PostgreSQL; monitorizar la tabla `login_registroauditoria`.
7. Política de contraseñas y revisión periódica de la auditoría; plantear 2FA si el despliegue es expuesto.

---

## Checklist de validación manual

**Antes de empezar:** ejecutar `migrate` y `makeadmin` (sección 8).

- [ ] `python manage.py check` → sin problemas.
- [ ] `python manage.py test login` → 66 tests OK.
- [ ] Abrir `http://127.0.0.1:8000/` sin sesión → formulario de login visible.
- [ ] Login con correo/contraseña de administrador → dashboard con estadísticas y directorio.
- [ ] Login con contraseña incorrecta 5 veces → mensaje "Demasiados intentos fallidos".
- [ ] Sidebar de **administrador** muestra: Inicio, Empleados, Departamentos, Mi perfil, *Administración* (Nuevo empleado, Auditoría).
- [ ] Sidebar de **empleado** muestra solo: Inicio, Empleados, Departamentos, Mi perfil.
- [ ] Como administrador: crear empleado `/empleados/nuevo/` → aparece en el listado; su contraseña permite el login.
- [ ] Como administrador: editar empleado, asignar rol (promover/degradar), restablecer contraseña, activar/desactivar.
- [ ] Como administrador: intentar desactivar/eliminar tu propia cuenta → mensaje de error, sin cambios.
- [ ] Como administrador: intentar degradar/demotar dejando cero administradores activos → bloqueado.
- [ ] Como empleado: intentar `/empleados/nuevo/`, `/empleados/<id>/editar/`, `/departamentos/nuevo/`, `/auditoria/` (introduciendo la URL a mano) → **403 "Acceso denegado"**.
- [ ] Como empleado: `/perfil/` → ver datos, editar nombre/correo, cambiar contraseña (pide la actual).
- [ ] Crear departamento, editarlo; intentar borrar uno con empleados → mensaje de bloqueo; borrar uno vacío → OK.
- [ ] Buscador y paginación en `/empleados/` y `/departamentos/`.
- [ ] `POST /logout/` cierra la sesión; `GET /logout/` no cierra nada.
- [ ] `/auditoria/` muestra los eventos (logins, creaciones, ediciones, eliminaciones) con filtros.
- [ ] URL inexistente → página 404 personalizada.
- [ ] Sin sesión, cualquier URL de módulo → redirige al login.

---

*Fin del levantamiento. Resumen: 3 modelos, 6 módulos con CRUD completo, 2 roles con mínimo privilegio, 66/66 pruebas superadas, 1 migración pendiente de aplicar por el usuario (`migrate` + `makeadmin`).*
