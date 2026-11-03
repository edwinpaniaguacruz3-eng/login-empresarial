from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .decorators import admin_requerido, get_empleado_sesion, login_requerido, puede_gestionar
from .forms import (
    ContrasenaAdminForm,
    ContrasenaPropiaForm,
    DepartamentoForm,
    EmpleadoForm,
    EmpleadoPerfilForm,
    EmpleadoRolForm,
    ProveedorForm,
)
from .models import Departamento, Empleado, Proveedor, RegistroAuditoria, ROL_ADMIN, ROL_EMPLEADO

# --- Protección básica contra fuerza bruta en el login ---
LOGIN_MAX_INTENTOS = 5
LOGIN_BLOQUEO_SEGUNDOS = 300

# --- Paginación ---
EMPLEADOS_POR_PAGINA = 10
DEPARTAMENTOS_POR_PAGINA = 10
PROVEEDORES_POR_PAGINA = 10
AUDITORIA_POR_PAGINA = 15

# --- Roles y matriz de permisos (refleja los decoradores reales de las vistas) ---
# (módulo, operación, puede_empleado, puede_administrador)
MATRIZ_PERMISOS = [
    ('Inicio', 'Ver el dashboard, estadísticas y directorio', True, True),
    ('Empleados (usuarios)', 'Consultar listado y detalle', True, True),
    ('Empleados (usuarios)', 'Crear, editar, desactivar/reactivar, asignar rol y restablecer contraseña', False, True),
    ('Departamentos (sucursales)', 'Consultar listado y detalle', True, True),
    ('Departamentos (sucursales)', 'Crear, editar, desactivar/reactivar', False, True),
    ('Proveedores', 'Consultar listado, detalle, buscar y filtrar', True, True),
    ('Proveedores', 'Crear, editar, desactivar/reactivar', False, True),
    ('Mi perfil', 'Ver y editar datos propios y cambiar contraseña', True, True),
    ('Roles y permisos', 'Consultar roles y matriz de permisos', False, True),
    ('Auditoría', 'Consultar el registro de auditoría', False, True),
]

INFO_ROLES = [
    (ROL_EMPLEADO, 'Empleado',
     'Rol por defecto (principio de mínimo privilegio). Consulta el '
     'directorio, departamentos y proveedores, y gestiona su propio '
     'perfil. No accede a ninguna administración.'),
    (ROL_ADMIN, 'Administrador',
     'Gestiona usuarios, roles, departamentos y proveedores; restablece '
     'contraseñas y revisa la auditoría. La asignación de roles se '
     'realiza desde la ficha de cada empleado.'),
]


# ============================================================
# Utilidades
# ============================================================

def _ip_cliente(request):
    """Obtiene la IP del cliente.

    X-Forwarded-For solo se respeta si TRUST_X_FORWARDED_FOR=True en settings
    (es decir, cuando la app corre detrás de un proxy de confianza). Si no,
    cualquier cliente podría falsificar la cabecera para esquivar el bloqueo
    por intentos fallidos del login.
    """
    if getattr(settings, 'TRUST_X_FORWARDED_FOR', False):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _clave_intentos(request, usuario_input):
    """Clave de caché para contar intentos fallidos (IP + usuario)."""
    return 'login_intentos:{}:{}'.format(_ip_cliente(request), usuario_input.strip().lower())


def _esta_bloqueado(clave):
    from django.core.cache import cache
    try:
        return cache.get(clave, 0) >= LOGIN_MAX_INTENTOS
    except Exception:
        # Si la caché no está disponible, nunca bloqueamos el login
        return False


def _registrar_intento_fallido(clave):
    from django.core.cache import cache
    try:
        cache.set(clave, cache.get(clave, 0) + 1, timeout=LOGIN_BLOQUEO_SEGUNDOS)
    except Exception:
        pass


def _limpiar_intentos(clave):
    from django.core.cache import cache
    try:
        cache.delete(clave)
    except Exception:
        pass


def _auditar(request, modulo, accion, detalle='', usuario=None):
    """Registra una acción en la auditoría (nunca almacena contraseñas)."""
    try:
        actor = usuario or getattr(request, 'empleado_sesion', None)
        RegistroAuditoria.objects.create(
            usuario=actor.nombre_completo if actor else 'Sistema',
            modulo=modulo,
            accion=accion,
            detalle=detalle[:1000],
            ip=_ip_cliente(request),
        )
    except Exception:
        # La auditoría nunca debe romper la operación principal
        pass


def _paginar(request, qs, por_pagina):
    """Pagina un queryset y devuelve el objeto de página."""
    paginator = Paginator(qs, por_pagina)
    numero = request.GET.get('page', 1)
    try:
        return paginator.page(numero)
    except Exception:
        return paginator.page(1)



# Login, dashboard y logout


def home(request):
    # Procesar el envío del formulario de Login (POST)
    if request.method == 'POST':
        usuario_input = (request.POST.get('username') or '').strip()
        password_input = request.POST.get('password') or ''

        clave_intentos = _clave_intentos(request, usuario_input)

        if _esta_bloqueado(clave_intentos):
            from django.contrib import messages
            messages.error(request, 'Demasiados intentos fallidos. Inténtalo de nuevo más tarde.')
            return render(request, 'login/index.html')

        # Buscar empleado ACTIVO por correo o nombre de usuario
        empleado_encontrado = Empleado.objects.filter(
            activo=True,
        ).filter(
            Q(correo__iexact=usuario_input) | Q(nombre__iexact=usuario_input)
        ).first()

        # Validar la contraseña contra el hash almacenado
        if empleado_encontrado and empleado_encontrado.check_password(password_input):
            _limpiar_intentos(clave_intentos)

            # Rotar la clave de sesión para prevenir fixación de sesión
            request.session.cycle_key()
            request.session['usuario_id'] = empleado_encontrado.id
            request.session['usuario_nombre'] = empleado_encontrado.nombre_completo
            _auditar(request, 'sesion', 'login_ok',
                     f"Inicio de sesión de {empleado_encontrado.correo}",
                     usuario=empleado_encontrado)
            from django.contrib import messages
            messages.success(
                request,
                f'Bienvenido, {empleado_encontrado.nombre_completo}.',
            )
            return redirect('home')
        else:
            _registrar_intento_fallido(clave_intentos)
            from django.contrib import messages
            messages.error(request, "Credenciales inválidas. Inténtalo de nuevo.")
            return render(request, 'login/index.html')

    # Si NO ha iniciado sesión, mostrar el formulario de Login (GET)
    if 'usuario_id' not in request.session:
        return render(request, 'login/index.html')

    empleado = get_empleado_sesion(request)
    if empleado is None:
        # Sesión huérfana (empleado eliminado o desactivado): cerrarla
        request.session.flush()
        return redirect('home')

    # --- LÓGICA DEL DASHBOARD ---
    query = request.GET.get('q', '').strip()

    # Directorio operativo: solo empleados activos. Los inactivos
    # se conservan y pueden consultarse en /empleados/?estado=inactivos.
    empleados_qs = Empleado.objects.select_related('departamento').filter(
        activo=True
    ).order_by('-id')

    if query:
        empleados_qs = empleados_qs.filter(
            Q(nombre__icontains=query) |
            Q(apellido__icontains=query) |
            Q(puesto__icontains=query) |
            Q(departamento__nombre__icontains=query)
        )

    pagina_empleados = _paginar(request, empleados_qs, EMPLEADOS_POR_PAGINA)

    # Estadísticas para los contadores superiores (consulta agregada)
    estadisticas = Empleado.objects.aggregate(
        total_empleados=Count('id'),
        empleados_activos=Count('id', filter=Q(activo=True)),
    )
    total_departamentos = Departamento.objects.count()

    context = {
        'usuario_nombre': empleado.nombre_completo,
        'total_empleados': estadisticas['total_empleados'],
        'total_departamentos': total_departamentos,
        'empleados_activos': estadisticas['empleados_activos'],
        'page_obj': pagina_empleados,
        'query_busqueda': query,
    }

    return render(request, 'login/dashboard.html', context)


@require_POST
@login_requerido
def logout_view(request):
    nombre = getattr(request, 'empleado_sesion', None)
    _auditar(request, 'sesion', 'logout', f"Cierre de sesión de {nombre.nombre_completo}" if nombre else 'Cierre de sesión')
    # Limpiar las variables de la sesión y eliminar la cookie
    request.session.flush()
    from django.contrib import messages
    messages.success(request, 'Has cerrado sesión correctamente.')
    return redirect('home')


# ============================================================
# CRUD de Empleados
# ============================================================

@login_requerido
def empleado_list(request):
    query = request.GET.get('q', '').strip()
    # Filtro de estado: activos (por defecto), inactivos o todos
    estado = request.GET.get('estado', 'activos').strip().lower()
    if estado not in ('activos', 'inactivos', 'todos'):
        estado = 'activos'
    qs = Empleado.objects.select_related('departamento').order_by('apellido', 'nombre')
    if estado == 'inactivos':
        qs = qs.filter(activo=False)
    elif estado == 'todos':
        pass  # histórico: activos + inactivos
    else:
        qs = qs.filter(activo=True)
    if query:
        qs = qs.filter(
            Q(nombre__icontains=query) |
            Q(apellido__icontains=query) |
            Q(correo__icontains=query) |
            Q(puesto__icontains=query) |
            Q(departamento__nombre__icontains=query)
        )
    return render(request, 'login/empleado_list.html', {
        'page_obj': _paginar(request, qs, EMPLEADOS_POR_PAGINA),
        'query_busqueda': query,
        'estado_actual': estado,
        'es_administrador': getattr(request, 'empleado_sesion').es_administrador,
    })


@login_requerido
def empleado_detail(request, pk):
    empleado = get_object_or_404(Empleado.objects.select_related('departamento'), pk=pk)
    return render(request, 'login/empleado_detail.html', {
        'empleado': empleado,
        'es_administrador': getattr(request, 'empleado_sesion').es_administrador,
    })


@admin_requerido
def empleado_create(request):
    if request.method == 'POST':
        form = EmpleadoForm(request.POST, requerir_password=True)
        if form.is_valid():
            empleado = form.save(commit=False)
            empleado.set_password(form.cleaned_data['password'])
            empleado.save()
            _auditar(request, 'empleado', 'crear',
                     f"Creó al empleado {empleado.nombre_completo} ({empleado.correo})")
            from django.contrib import messages
            messages.success(request, f'Empleado "{empleado.nombre_completo}" creado correctamente.')
            return redirect('empleado_detail', pk=empleado.pk)
    else:
        form = EmpleadoForm(requerir_password=True)
    return render(request, 'login/empleado_form.html', {
        'form': form,
        'titulo': 'Crear empleado',
        'accion': 'Crear',
    })


@admin_requerido
def empleado_update(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if request.method == 'POST':
        form = EmpleadoForm(request.POST, instance=empleado)
        if form.is_valid():
            datos_empleado = form.save(commit=False)
            nueva_password = form.cleaned_data.get('password')
            if nueva_password:
                datos_empleado.set_password(nueva_password)
                detalle = f"Editó al empleado {datos_empleado.nombre_completo} y le cambió la contraseña"
            else:
                detalle = f"Editó al empleado {datos_empleado.nombre_completo}"
            # No se puede desactivar el propio usuario (evita auto-bloqueo)
            if datos_empleado.pk == request.empleado_sesion.pk and not datos_empleado.activo:
                form.add_error('activo', 'No puedes desactivar tu propia cuenta.')
                return render(request, 'login/empleado_form.html', {
                    'form': form, 'titulo': 'Editar empleado', 'accion': 'Guardar',
                    'empleado': empleado,
                })
            datos_empleado.save()
            _auditar(request, 'empleado', 'editar', detalle)
            from django.contrib import messages
            messages.success(request, f'Empleado "{datos_empleado.nombre_completo}" actualizado correctamente.')
            return redirect('empleado_detail', pk=datos_empleado.pk)
    else:
        form = EmpleadoForm(instance=empleado)
    return render(request, 'login/empleado_form.html', {
        'form': form,
        'titulo': 'Editar empleado',
        'accion': 'Guardar',
        'empleado': empleado,
    })


@admin_requerido
def empleado_delete(request, pk):
    """Desactivación lógica: conserva el registro, su PK y sus relaciones."""
    empleado = get_object_or_404(Empleado, pk=pk)
    # Protección: no puedes desactivar tu propia cuenta
    if empleado.pk == request.empleado_sesion.pk:
        from django.contrib import messages
        messages.error(request, 'No puedes desactivar tu propia cuenta.')
        return redirect('empleado_detail', pk=empleado.pk)
    # Protección: debe quedar al menos un administrador activo
    if empleado.es_administrador and empleado.activo:
        admins_restantes = Empleado.objects.filter(
            rol='admin',
            activo=True,
        ).exclude(pk=empleado.pk).count()
        if admins_restantes == 0:
            from django.contrib import messages
            messages.error(
                request,
                f'No se puede desactivar a "{empleado.nombre_completo}": '
                'es el único administrador activo. Promueve otro empleado primero.',
            )
            return redirect('empleado_detail', pk=empleado.pk)
    if request.method == 'POST':
        if not empleado.activo:
            from django.contrib import messages
            messages.info(
                request,
                f'"{empleado.nombre_completo}" ya está desactivado.',
            )
            return redirect('empleado_detail', pk=empleado.pk)
        nombre = empleado.nombre_completo
        # Desactivación lógica (nunca borrado físico)
        empleado.activo = False
        empleado.save()
        _auditar(request, 'empleado', 'desactivar', f"Desactivó al empleado {nombre}")
        from django.contrib import messages
        messages.success(
            request,
            f'Empleado "{nombre}" desactivado. Sus datos se conservan '
            'y podrás reactivarlo desde "Rol y estado".',
        )
        return redirect('empleado_list')
    return render(request, 'login/empleado_confirm_delete.html', {'empleado': empleado})


@admin_requerido
def empleado_rol(request, pk):
    """Asignación de rol y estado de cuenta (solo administradores)."""
    empleado = get_object_or_404(Empleado, pk=pk)
    # No puedes cambiar tu propio rol (evita auto-bloqueo y escalada involuntaria)
    if empleado.pk == request.empleado_sesion.pk:
        from django.contrib import messages
        messages.error(
            request,
            'No puedes modificar tu propio rol ni tu propio estado. '
            'Pide a otro administrador que lo haga.',
        )
        return redirect('empleado_detail', pk=empleado.pk)
    if request.method == 'POST':
        # Se leen ANTES de validar: ModelForm copia los valores sobre la
        # instancia durante is_valid() (construct_instance), así que después
        # ya no se conoce el rol ni el estado previos.
        estaba_activo = empleado.activo
        rol_anterior = empleado.rol
        form = EmpleadoRolForm(request.POST, instance=empleado)
        if form.is_valid():
            nuevo_rol = form.cleaned_data['rol']
            nuevo_activo = form.cleaned_data['activo']
            # Protección del último administrador activo: aplica tanto si se
            # le quita el rol como si se le desactiva la cuenta.
            deja_de_ser_admin_activo = (
                rol_anterior == 'admin' and estaba_activo
                and (nuevo_rol != 'admin' or not nuevo_activo)
            )
            if deja_de_ser_admin_activo:
                admins_restantes = Empleado.objects.filter(
                    rol='admin', activo=True
                ).exclude(pk=empleado.pk).count()
                if admins_restantes == 0:
                    form.add_error(
                        'rol',
                        'No puedes quitar el rol ni desactivar al último '
                        'administrador activo. Promueve otro empleado primero.',
                    )
                    return render(request, 'login/empleado_rol.html', {
                        'form': form, 'empleado': empleado,
                    })
            form.save()
            if not estaba_activo and form.cleaned_data['activo']:
                _auditar(request, 'empleado', 'reactivar',
                         f"Reactivó al empleado {empleado.nombre_completo}")
            else:
                _auditar(request, 'empleado', 'estado',
                         f"Cambió rol a '{form.cleaned_data['rol']}' y estado "
                         f"activo={form.cleaned_data['activo']} de {empleado.nombre_completo}")
            from django.contrib import messages
            messages.success(
                request,
                f"Rol y estado de \"{empleado.nombre_completo}\" actualizados correctamente.",
            )
            return redirect('empleado_detail', pk=empleado.pk)
    else:
        form = EmpleadoRolForm(instance=empleado)
    return render(request, 'login/empleado_rol.html', {
        'form': form,
        'empleado': empleado,
    })


@admin_requerido
def empleado_contrasena(request, pk):
    """Restablecimiento de contraseña de otro empleado (solo administradores)."""
    empleado = get_object_or_404(Empleado, pk=pk)
    if request.method == 'POST':
        form = ContrasenaAdminForm(request.POST)
        if form.is_valid():
            empleado.set_password(form.cleaned_data['password_nueva'])
            empleado.save()
            _auditar(request, 'empleado', 'contrasena',
                     f"Restableció la contraseña de {empleado.nombre_completo}")
            from django.contrib import messages
            messages.success(
                request,
                f'Contraseña de "{empleado.nombre_completo}" actualizada correctamente.',
            )
            return redirect('empleado_detail', pk=empleado.pk)
    else:
        form = ContrasenaAdminForm()
    return render(request, 'login/empleado_contrasena.html', {
        'form': form,
        'empleado': empleado,
    })


# ============================================================
# CRUD de Departamentos
# ============================================================

@login_requerido
def departamento_list(request):
    query = request.GET.get('q', '').strip()
    # Filtro de estado: activos (por defecto), inactivos o todos
    estado = request.GET.get('estado', 'activos').strip().lower()
    if estado not in ('activos', 'inactivos', 'todos'):
        estado = 'activos'
    qs = Departamento.objects.annotate(
        total_empleados=Count('empleados')
    ).order_by('nombre')
    if estado == 'inactivos':
        qs = qs.filter(activo=False)
    elif estado == 'todos':
        pass  # histórico: activos + inactivos
    else:
        qs = qs.filter(activo=True)
    if query:
        qs = qs.filter(nombre__icontains=query)
    return render(request, 'login/departamento_list.html', {
        'page_obj': _paginar(request, qs, DEPARTAMENTOS_POR_PAGINA),
        'query_busqueda': query,
        'estado_actual': estado,
        'es_administrador': getattr(request, 'empleado_sesion').es_administrador,
    })


@login_requerido
def departamento_detail(request, pk):
    departamento = get_object_or_404(
        Departamento.objects.annotate(total_empleados=Count('empleados')), pk=pk
    )
    empleados = departamento.empleados.select_related('departamento').order_by('apellido', 'nombre')
    return render(request, 'login/departamento_detail.html', {
        'departamento': departamento,
        'page_obj': _paginar(request, empleados, EMPLEADOS_POR_PAGINA),
        'es_administrador': getattr(request, 'empleado_sesion').es_administrador,
    })


@admin_requerido
def departamento_create(request):
    if request.method == 'POST':
        form = DepartamentoForm(request.POST)
        if form.is_valid():
            departamento = form.save()
            _auditar(request, 'departamento', 'crear', f"Creó el departamento {departamento.nombre}")
            from django.contrib import messages
            messages.success(request, f'Departamento "{departamento.nombre}" creado correctamente.')
            return redirect('departamento_detail', pk=departamento.pk)
    else:
        form = DepartamentoForm()
    return render(request, 'login/departamento_form.html', {
        'form': form,
        'titulo': 'Crear departamento',
        'accion': 'Crear',
    })


@admin_requerido
def departamento_update(request, pk):
    departamento = get_object_or_404(Departamento, pk=pk)
    if request.method == 'POST':
        form = DepartamentoForm(request.POST, instance=departamento)
        if form.is_valid():
            datos = form.save()
            _auditar(request, 'departamento', 'editar', f"Editó el departamento {datos.nombre}")
            from django.contrib import messages
            messages.success(request, f'Departamento "{datos.nombre}" actualizado correctamente.')
            return redirect('departamento_detail', pk=datos.pk)
    else:
        form = DepartamentoForm(instance=departamento)
    return render(request, 'login/departamento_form.html', {
        'form': form,
        'titulo': 'Editar departamento',
        'accion': 'Guardar',
        'departamento': departamento,
    })


@admin_requerido
def departamento_delete(request, pk):
    """Desactivación lógica: sin borrado en cascada, se conservan empleados."""
    departamento = get_object_or_404(Departamento, pk=pk)
    if request.method == 'POST':
        if not departamento.activo:
            from django.contrib import messages
            messages.info(
                request,
                f'"{departamento.nombre}" ya está desactivado.',
            )
            return redirect('departamento_detail', pk=departamento.pk)
        nombre = departamento.nombre
        # Desactivación lógica: no hay borrado en cascada de empleados
        departamento.activo = False
        departamento.save()
        _auditar(request, 'departamento', 'desactivar', f"Desactivó el departamento {nombre}")
        from django.contrib import messages
        messages.success(
            request,
            f'Departamento "{nombre}" desactivado. Se conservan sus datos '
            'y sus empleados asignados; podrás reactivarlo cuando quieras.',
        )
        return redirect('departamento_list')
    return render(request, 'login/departamento_confirm_delete.html', {'departamento': departamento})


@require_POST
@admin_requerido
def departamento_reactivar(request, pk):
    """Reactiva un departamento desactivado (misma PK y relaciones)."""
    departamento = get_object_or_404(Departamento, pk=pk)
    if departamento.activo:
        from django.contrib import messages
        messages.info(request, f'"{departamento.nombre}" ya está activo.')
    else:
        departamento.activo = True
        departamento.save()
        _auditar(request, 'departamento', 'reactivar',
                 f"Reactivó el departamento {departamento.nombre}")
        from django.contrib import messages
        messages.success(
            request,
            f'Departamento "{departamento.nombre}" reactivado correctamente.',
        )
    return redirect('departamento_detail', pk=departamento.pk)


# ============================================================
# CRUD de Proveedores
# ============================================================

@login_requerido
def proveedor_list(request):
    query = request.GET.get('q', '').strip()
    # Filtro de estado: activos (por defecto), inactivos o todos
    estado = request.GET.get('estado', 'activos').strip().lower()
    if estado not in ('activos', 'inactivos', 'todos'):
        estado = 'activos'
    qs = Proveedor.objects.order_by('nombre')
    if estado == 'inactivos':
        qs = qs.filter(activo=False)
    elif estado == 'todos':
        pass  # histórico: activos + inactivos
    else:
        qs = qs.filter(activo=True)
    if query:
        qs = qs.filter(
            Q(nombre__icontains=query) |
            Q(contacto__icontains=query) |
            Q(correo__icontains=query)
        )
    return render(request, 'login/proveedor_list.html', {
        'page_obj': _paginar(request, qs, PROVEEDORES_POR_PAGINA),
        'query_busqueda': query,
        'estado_actual': estado,
        'es_administrador': getattr(request, 'empleado_sesion').es_administrador,
    })


@login_requerido
def proveedor_detail(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    return render(request, 'login/proveedor_detail.html', {
        'proveedor': proveedor,
        'es_administrador': getattr(request, 'empleado_sesion').es_administrador,
    })


@admin_requerido
def proveedor_create(request):
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            proveedor = form.save()
            _auditar(request, 'proveedor', 'crear',
                     f"Creó el proveedor {proveedor.nombre}")
            from django.contrib import messages
            messages.success(request, f'Proveedor "{proveedor.nombre}" creado correctamente.')
            return redirect('proveedor_detail', pk=proveedor.pk)
    else:
        form = ProveedorForm()
    return render(request, 'login/proveedor_form.html', {
        'form': form,
        'titulo': 'Crear proveedor',
        'accion': 'Crear',
    })


@admin_requerido
def proveedor_update(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            datos = form.save()
            _auditar(request, 'proveedor', 'editar', f"Editó el proveedor {datos.nombre}")
            from django.contrib import messages
            messages.success(request, f'Proveedor "{datos.nombre}" actualizado correctamente.')
            return redirect('proveedor_detail', pk=datos.pk)
    else:
        form = ProveedorForm(instance=proveedor)
    return render(request, 'login/proveedor_form.html', {
        'form': form,
        'titulo': 'Editar proveedor',
        'accion': 'Guardar',
        'proveedor': proveedor,
    })


@admin_requerido
def proveedor_delete(request, pk):
    """Desactivación lógica: conserva el registro, su PK y sus datos."""
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        if not proveedor.activo:
            from django.contrib import messages
            messages.info(
                request,
                f'"{proveedor.nombre}" ya está desactivado.',
            )
            return redirect('proveedor_detail', pk=proveedor.pk)
        nombre = proveedor.nombre
        # Desactivación lógica (nunca borrado físico)
        proveedor.activo = False
        proveedor.save()
        _auditar(request, 'proveedor', 'desactivar', f"Desactivó el proveedor {nombre}")
        from django.contrib import messages
        messages.success(
            request,
            f'Proveedor "{nombre}" desactivado. Se conservan sus datos; '
            'podrás reactivarlo cuando quieras.',
        )
        return redirect('proveedor_list')
    return render(request, 'login/proveedor_confirm_delete.html', {'proveedor': proveedor})


@require_POST
@admin_requerido
def proveedor_reactivar(request, pk):
    """Reactiva un proveedor desactivado (misma PK y datos)."""
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if proveedor.activo:
        from django.contrib import messages
        messages.info(request, f'"{proveedor.nombre}" ya está activo.')
    else:
        proveedor.activo = True
        proveedor.save()
        _auditar(request, 'proveedor', 'reactivar',
                 f"Reactivó el proveedor {proveedor.nombre}")
        from django.contrib import messages
        messages.success(
            request,
            f'Proveedor "{proveedor.nombre}" reactivado correctamente.',
        )
    return redirect('proveedor_detail', pk=proveedor.pk)


# ============================================================
# Roles y permisos (consulta)
# ============================================================

@admin_requerido
def roles_list(request):
    """Consulta de roles y la matriz de permisos del sistema.

    El sistema tiene dos roles de negocio fijos sobre el campo
    `rol` de Empleado (empleado/admin). La asignación y retirada
    de permisos se realiza por empleado desde su ficha
    (empleado_rol); no existe un segundo sistema de roles.
    """
    return render(request, 'login/roles_list.html', {
        'roles': INFO_ROLES,
        'matriz': MATRIZ_PERMISOS,
        'total_administradores': Empleado.objects.filter(
            rol=ROL_ADMIN, activo=True
        ).count(),
        'total_empleados': Empleado.objects.filter(activo=True).count(),
    })


# ============================================================
# Perfil propio
# ============================================================

@login_requerido
def perfil(request):
    return render(request, 'login/perfil.html', {
        'empleado': request.empleado_sesion,
    })


@login_requerido
def perfil_editar(request):
    empleado = request.empleado_sesion
    if request.method == 'POST':
        form = EmpleadoPerfilForm(request.POST, instance=empleado)
        if form.is_valid():
            datos = form.save()
            _auditar(request, 'perfil', 'editar',
                     f"Actualizó su perfil ({datos.nombre_completo})")
            from django.contrib import messages
            messages.success(request, 'Tu perfil se actualizó correctamente.')
            # Mantener la sesión sincronizada con el nuevo nombre
            request.session['usuario_nombre'] = datos.nombre_completo
            return redirect('perfil')
    else:
        form = EmpleadoPerfilForm(instance=empleado)
    return render(request, 'login/perfil_editar.html', {'form': form})


@login_requerido
def perfil_contrasena(request):
    empleado = request.empleado_sesion
    if request.method == 'POST':
        form = ContrasenaPropiaForm(request.POST, empleado=empleado)
        if form.is_valid():
            empleado.set_password(form.cleaned_data['password_nueva'])
            empleado.save()
            _auditar(request, 'perfil', 'contrasena', 'Cambió su propia contraseña')
            from django.contrib import messages
            messages.success(
                request,
                'Tu contraseña se actualizó correctamente.',
            )
            return redirect('perfil')
    else:
        form = ContrasenaPropiaForm(empleado=empleado)
    return render(request, 'login/perfil_contrasena.html', {'form': form})


# ============================================================
# Auditoría (solo administradores)
# ============================================================

@admin_requerido
def auditoria_list(request):
    qs = RegistroAuditoria.objects.all()
    modulo = request.GET.get('modulo', '').strip()
    accion = request.GET.get('accion', '').strip()
    if modulo:
        qs = qs.filter(modulo=modulo)
    if accion:
        qs = qs.filter(accion=accion)
    return render(request, 'login/auditoria_list.html', {
        'page_obj': _paginar(request, qs, AUDITORIA_POR_PAGINA),
        'modulo_actual': modulo,
        'accion_actual': accion,
        'modulos': RegistroAuditoria.MODULOS,
        'acciones': RegistroAuditoria.ACCIONES,
    })


# ============================================================
# Páginas de error
# ============================================================

def handler403(request, exception=None):
    return render(request, 'login/403.html', status=403)


def handler404(request, exception=None):
    return render(request, 'login/404.html', status=404)


def handler500(request):
    return render(request, 'login/500.html', status=500)