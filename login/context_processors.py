"""Context processor: expone el empleado de la sesión a todas las plantillas."""
from .decorators import get_empleado_sesion


def sesion_actual(request):
    empleado = get_empleado_sesion(request)

    # Módulo activo (para resaltar el item del sidebar)
    modulo = ''
    match = getattr(request, 'resolver_match', None)
    if match and match.url_name:
        nombre = match.url_name
        if nombre == 'home':
            modulo = 'inicio'
        elif nombre == 'empleado_create':
            modulo = 'nuevo_empleado'
        elif nombre.startswith('empleado'):
            modulo = 'empleados'
        elif nombre.startswith('departamento'):
            modulo = 'departamentos'
        elif nombre.startswith('proveedor'):
            modulo = 'proveedores'
        elif nombre.startswith('rol'):
            modulo = 'roles'
        elif nombre.startswith('perfil'):
            modulo = 'perfil'
        elif nombre == 'auditoria_list':
            modulo = 'auditoria'

    return {
        'empleado_sesion': empleado,
        'es_administrador': bool(empleado and empleado.es_administrador),
        'usuario_sesion_nombre': empleado.nombre_completo if empleado else '',
        'modulo_activo': modulo,
    }
