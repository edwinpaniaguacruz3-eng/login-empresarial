# INFORME DE INTERVENCIÓN — Módulos de administración (Usuarios, Roles y permisos, Sucursales, Proveedores)

**Proyecto:** `proyecto_menu` (panel VOLTRIX) · Python 3.14.5 + Django 6.1.1 + PostgreSQL
**Fecha:** 2026-10-12
**Alcance:** Completar los módulos de administración solicitados sin rediseñar el sistema.
**Regla principal respetada:** NO se rediseñó, reconstruyó ni reemplazó el dashboard ni el diseño visual.

---

## 1. Inspección previa (estado del proyecto)

El proyecto es una aplicación de gestión de empleados y departamentos con autenticación propia
por sesión (modelo personalizado `Empleado`, **no** `django.contrib.auth.User`), con:

- `Empleado` (usuarios del sistema): nombre, apellido, correo (único), puesto, FK a
  `Departamento`, `fecha_ingreso`, `activo`, `rol` (`empleado`/`admin`), `password`
  (hash PBKDF2 vía `make_password`/`check_password`).
- `Departamento`: nombre (único), descripción, `activo` (desactivación lógica).
- `RegistroAuditoria`: historial inmutable de acciones (solo escritura desde el servidor).
- Decoradores propios: `login_requerido`, `admin_requerido`, `puede_gestionar`.
- Desactivación lógica en place de borrado físico (convención del proyecto desde 2026-10-11).
- 77 pruebas automatizadas funcionando antes de esta intervención.

BD real (PostgreSQL local `db_login`): 3 empleados (1 administrador) y 2 departamentos.
**Ningún registro fue modificado ni eliminado.**

## 2. Mapeo de las cuatro opciones solicitadas

| Opción solicitada | Estado encontrado | Acción tomada |
|---|---|---|
| **Usuarios** | Ya existe como módulo **Empleados** (`/empleados/`): listado, detalle, crear, editar, activar/desactivar, asignar rol, relacionar con departamentos (sucursales), restablecer contraseña, validación completa. Utiliza el modelo personalizado actual. | **Reutilizado sin duplicar.** No se creó un módulo ni un modelo nuevo. |
| **Sucursales** | Ya existe como módulo **Departamentos** (`/departamentos/`): unidad organizativa con listado, detalle, crear, editar, estado (activo/inactivo), empleados relacionados y reactivación. | **Reutilizado sin duplicar.** Las relaciones usuario↔sucursal son `Empleado.departamento`. |
| **Roles y permisos** | La **asignación** de roles existe (`/empleados/<pk>/rol/`, campo `rol`), pero no había consulta de roles ni matriz de permisos. El sistema usa un mecanismo propio (no grupos de Django). | **Completado** con una página de consulta real (`/roles/`) que reutiliza el mecanismo existente. No se creó un segundo sistema de roles. |
| **Proveedores** | No existía. | **Implementado** nuevo módulo completo (modelo, migración aditiva, CRUD, búsqueda/filtros, estado, plantillas, menú, pruebas). |

## 3. Cambios realizados

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `login/models.py` | Nuevo modelo `Proveedor` (nombre único, contacto, correo, teléfono, dirección, fecha_alta, activo) y opción `('proveedor', 'Proveedores')` en `RegistroAuditoria.MODULOS`. |
| `login/migrations/0005_proveedor_alter_registroauditoria_modulo.py` | Migración **no destructiva**: crea la tabla `login_proveedor` y actualiza los `choices` de `modulo` (no reescribe datos). **Ya aplicada** en la BD local de desarrollo (`manage.py migrate login` → OK). |
| `login/forms.py` | Nuevo `ProveedorForm` (validación de obligatoriedad y unicidad insensible a mayúsculas del nombre; campos opcionales limpios). |
| `login/views.py` | Vistas `proveedor_list/detail/create/update/delete/reactivar` y `roles_list`; constantes `PROVEEDORES_POR_PAGINA`, `MATRIZ_PERMISOS`, `INFO_ROLES`. |
| `login/urls.py` | 7 rutas nuevas: `/proveedores/…` (6) y `/roles/` (1). |
| `login/context_processors.py` | Resaltado del sidebar para `proveedor*` → `proveedores` y `rol*` → `roles`. |
| `login/admin.py` | `ProveedorAdmin` registrado con búsqueda/filtros y **sin permiso de borrado físico** (igual que Empleados y Departamentos). |
| `login/templates/login/base.html` | Dos elementos nuevos en el menú lateral con los mismos estilos/clases existentes: **Proveedores** (navegación principal, visible a todo usuario autenticado) y **Roles y permisos** (sección «Administración», solo administradores). |
| `login/tests.py` | 23 pruebas nuevas (CRUDProveedorTests, RolesPermisosTests). Total: **100 pruebas**. |

### Archivos creados (plantillas, todas extienden `base.html` con los patrones visuales actuales)

- `login/templates/login/proveedor_list.html` (listado + búsqueda + filtros de estado + paginación)
- `login/templates/login/proveedor_detail.html` (detalle con grid de datos y acciones)
- `login/templates/login/proveedor_form.html` (formulario crear/editar)
- `login/templates/login/proveedor_confirm_delete.html` (confirmación de desactivación)
- `login/templates/login/roles_list.html` (roles, matriz de permisos y nota de asignación)

**No se modificó ningún archivo CSS** (se reutilizaron clases existentes: `badge`, `chip`,
`filtro-estado`, `table-header`, `detail-grid`, `formulario`, `confirm-box`, etc.).
**No se tocaron** el dashboard, la paleta, la tipografía, ni los módulos de Empleados,
Departamentos, Perfil ni Auditoría.

## 4. Rutas implementadas

| Ruta | Nombre | Acceso |
|---|---|---|
| `/proveedores/` | `proveedor_list` | Autenticado (buscar `?q=`, filtrar `?estado=`) |
| `/proveedores/nuevo/` | `proveedor_create` | Administrador |
| `/proveedores/<pk>/` | `proveedor_detail` | Autenticado |
| `/proveedores/<pk>/editar/` | `proveedor_update` | Administrador |
| `/proveedores/<pk>/eliminar/` | `proveedor_delete` | Administrador (desactivación lógica) |
| `/proveedores/<pk>/reactivar/` | `proveedor_reactivar` | Administrador (solo POST) |
| `/roles/` | `roles_list` | Administrador (consulta) |

## 5. Seguridad y reglas de negocio aplicadas

- **Backend:** toda operación de escritura exige sesión (`login_requerido`) y, para
  gestión, rol de administrador (`admin_requerido` → `PermissionDenied` → `handler403`).
  Ocultar botones en plantillas no es el mecanismo de control.
- **CSRF:** todas las vistas POST usan `{% csrf_token %}`; los cambios de estado solo se
  ejecutan por POST (`@require_POST` en reactivar; logout sigue siendo POST).
- **Contraseñas:** sin cambios; siguen hasheadas con PBKDF2 (nunca texto plano).
- **Desactivación lógica:** `proveedor_delete` pone `activo=False` (conserva PK y datos),
  es idempotente y se puede revertir con `proveedor_reactivar`. No hay borrado físico
  ni en la app ni en `/admin/`.
- **Duplicados:** `nombre` único a nivel de BD y validado insensible a mayúsculas
  con mensaje amigable.
- **Auditoría:** cada operación de proveedores se registra en `RegistroAuditoria`
  con el actor real de la sesión y la IP (módulo `proveedor`).
- **Último administrador:** las protecciones existentes (no modificar el propio rol,
  no desactivarse a sí mismo, siempre queda ≥1 administrador activo) permanecen intactas.

## 6. Decisiones documentadas (conflictos y restricciones)

1. **Usuarios/Sucursales existen bajo otros nombres.** Añadir entradas duplicadas en el
   menú apuntando a las mismas vistas violaría la regla «evitar duplicados». Se
   reutilizan las implementaciones existentes (criterio de aceptación: las cuatro
   opciones están disponibles sin duplicados).
2. **No se crearon roles arbitrarios.** El sistema define dos roles de negocio fijos
   sobre `Empleado.rol`. Crear un modelo `Rol` con permisos granulares sería un
   segundo sistema de roles, lo que la propia tarea prohíbe. La página `/roles/`
   documenta esta decisión y enlaza a la asignación existente por empleado.
3. **`Proveedor` no tiene FK a Departamento.** El modelo actual no relaciona
   proveedores con unidades organizativas (no hay compras/inventario/facturas en el
   sistema); inventar esa relación sería crear una regla de negocio inexistente.

## 7. Pruebas ejecutadas y resultados

| Comprobación | Comando | Resultado |
|---|---|---|
| Checks del sistema | `manage.py check` | ✅ «System check identified no issues (0 silenced)» |
| Modelos vs migraciones | `manage.py makemigrations --check --dry-run` | ✅ «No changes detected» |
| Migración aplicada en BD local | `manage.py migrate login` | ✅ `Applying login.0005… OK` |
| Suite de pruebas (BD de pruebas PostgreSQL, `--keepdb`) | `manage.py test login --keepdb` | ✅ **Ran 100 tests — OK** (77 previas + 23 nuevas) |
| Resolución de URLs (26 rutas) | script de verificación | ✅ Todas resueltas |
| Smoke test de solo lectura contra BD real | Django `Client` (GET) | ✅ `/` → 200; módulos nuevos → 302 al login anónimo; `/proveedores/1/reactivar/` → 405 (solo POST); `/no-existe/` → 404 personalizado |

Nota: la primera ejecución de la suite reportó 4 fallos de las pruebas nuevas
(3 por limpieza de campos vacíos y 1 aserción que colisionaba con el mensaje de
éxito). Se corrigieron y la suite completa pasa. La BD de pruebas (`test_db_login`)
ya existía en el entorno; se usó `--keepdb` para no eliminarla (operación no destructiva).

## 8. Cómo aplicar en otro entorno

```powershell
.\venv\Scripts\Activate.ps1
python manage.py migrate          # aplica 0005 (solo crea tabla; no toca datos)
python manage.py test login --keepdb
python manage.py runserver
```

La migración es segura: solo crea `login_proveedor` y actualiza metadatos de `choices`.
No borra ni reescribe ninguna fila existente.

## 9. Pendientes (no bloqueantes, ajenos a esta tarea)

- Si se desea que el menú muestre literalmente las etiquetas «Usuarios» y «Sucursales»
  (en lugar de «Empleados» y «Departamentos»), es un cambio cosmético de etiquetas
  que conviene confirmar, pues implicaría navegación duplicada hacia las mismas vistas.
- Avisos de `check --deploy` preexistentes (secretos por entorno, HTTPS) siguen
  pendientes de producción, sin relación con esta intervención.
