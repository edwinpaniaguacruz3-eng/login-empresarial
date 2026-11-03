"""Decoradores de control de acceso basados en la sesión de Empleado.

Usan el mecanismo nativo de Django (wrappers de vistas al estilo de
django.contrib.auth.decorators) adaptado a la autenticación por sesión
propia de esta aplicación.
"""
from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .models import Empleado


def get_empleado_sesion(request):
    """Devuelve el Empleado activo de la sesión o None."""
    empleado_id = request.session.get('usuario_id')
    if not empleado_id:
        return None
    try:
        empleado = Empleado.objects.select_related('departamento').get(pk=empleado_id)
    except Empleado.DoesNotExist:
        return None
    # Un empleado desactivado pierde la sesión inmediatamente
    if not empleado.activo:
        return None
    return empleado


def login_requerido(view_func):
    """Redirige al login si no hay una sesión de empleado activa."""

    @wraps(view_func)
    def _wrapper(request, *args, **kwargs):
        empleado = get_empleado_sesion(request)
        if empleado is None:
            return redirect('home')
        request.empleado_sesion = empleado
        return view_func(request, *args, **kwargs)

    return _wrapper


def admin_requerido(view_func):
    """Exige sesión activa Y rol de administrador (HTTP 403 si no lo es)."""

    @wraps(view_func)
    def _wrapper(request, *args, **kwargs):
        empleado = get_empleado_sesion(request)
        if empleado is None:
            return redirect('home')
        if not empleado.es_administrador:
            messages.error(
                request,
                'Acceso denegado: necesitas permisos de administrador '
                'para esa sección.',
            )
            # Excepción nativa de Django: invoca handler403 (página personalizada)
            raise PermissionDenied()
        request.empleado_sesion = empleado
        return view_func(request, *args, **kwargs)

    return _wrapper


def puede_gestionar(empleado_actual):
    """Regla de negocio: solo un administrador activo gestiona datos.

    `empleado_actual`: Empleado que ejecuta la acción (el de la sesión).
    """
    return bool(empleado_actual and empleado_actual.activo and empleado_actual.es_administrador)
