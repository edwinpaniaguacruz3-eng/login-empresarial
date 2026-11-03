from django.db import models
from django.contrib.auth.hashers import check_password, make_password


# ---------- Roles ----------
# El proyecto ya tuvo un campo "rol" en su historial (ver .pyc antiguos en
# migrations/__pycache__); se recupera ahora sobre Empleado.
ROL_EMPLEADO = 'empleado'
ROL_ADMIN = 'admin'

ROLES = [
    (ROL_EMPLEADO, 'Empleado'),
    (ROL_ADMIN, 'Administrador'),
]


class Departamento(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    # Desactivación lógica: el registro se conserva (con su PK y sus
    # empleados asignados) pero deja de aparecer en los listados
    # operativos. `activo=False` equivale a una baja reversible.
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Departamento'
        verbose_name_plural = 'Departamentos'

    def __str__(self):
        return self.nombre


class Empleado(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    correo = models.EmailField(unique=True)
    puesto = models.CharField(max_length=100)
    departamento = models.ForeignKey(
        Departamento, on_delete=models.CASCADE, related_name='empleados'
    )
    fecha_ingreso = models.DateField(auto_now_add=True)
    activo = models.BooleanField(default=True)

    # Rol del empleado. Por defecto EMPLEADO (principio de mínimo privilegio).
    # Solo un administrador puede asignar/quitar el rol de administrador.
    rol = models.CharField(max_length=20, choices=ROLES, default=ROL_EMPLEADO)

    # Contraseña almacenada SIEMPRE hasheada (formato Django, p. ej. pbkdf2_...).
    # Nunca se guarda ni se muestra en texto plano.
    password = models.CharField(max_length=128, blank=True, default='')

    class Meta:
        ordering = ['apellido', 'nombre']
        verbose_name = 'Empleado'
        verbose_name_plural = 'Empleados'

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

    @property
    def es_administrador(self):
        return self.rol == ROL_ADMIN

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"

    def set_password(self, raw_password):
        """Almacena la contraseña hasheada."""
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        """Comprueba una contraseña en texto plano contra el hash almacenado."""
        if not self.password:
            return False
        return check_password(raw_password, self.password)

    @property
    def iniciales(self):
        inicial_nombre = self.nombre[0].upper() if self.nombre else ''
        inicial_apellido = self.apellido[0].upper() if self.apellido else ''
        return f"{inicial_nombre}{inicial_apellido}"


class Proveedor(models.Model):
    """Proveedor de la empresa (catálogo).

    Sigue las mismas convenciones que Departamento: nombre único,
    desactivación lógica (activo=False) en lugar de borrado físico,
    para conservar el registro, su PK y su historial.
    """

    nombre = models.CharField(max_length=100, unique=True)
    contacto = models.CharField(max_length=100, blank=True, null=True)
    correo = models.EmailField(blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    fecha_alta = models.DateField(auto_now_add=True)
    # Desactivación lógica: la baja es reversible (ver Departamento.activo).
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'

    def __str__(self):
        return self.nombre


class RegistroAuditoria(models.Model):
    """Registro histórico de acciones administrativas y de seguridad relevantes.

    Solo se escribe desde el servidor (nunca editable/borrable desde la UI).
    """

    ACCIONES = [
        ('login_ok', 'Inicio de sesión correcto'),
        ('logout', 'Cierre de sesión'),
        ('crear', 'Creación de registro'),
        ('editar', 'Edición de registro'),
        ('desactivar', 'Desactivación lógica'),
        ('reactivar', 'Reactivación de registro'),
        # 'eliminar' se conserva para que los registros históricos
        # de auditoría (borrado físico de fases anteriores) sigan
        # mostrándose con su etiqueta original.
        ('eliminar', 'Eliminación de registro'),
        ('contrasena', 'Cambio/restablecimiento de contraseña'),
        ('estado', 'Cambio de estado de cuenta'),
    ]

    MODULOS = [
        ('empleado', 'Empleados'),
        ('departamento', 'Departamentos'),
        ('proveedor', 'Proveedores'),
        ('sesion', 'Sesión'),
        ('perfil', 'Perfil propio'),
    ]

    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.CharField(max_length=200)  # Nombre del actor (no FK: sobrevive a borrados)
    modulo = models.CharField(max_length=20, choices=MODULOS)
    accion = models.CharField(max_length=20, choices=ACCIONES)
    detalle = models.TextField(blank=True)
    ip = models.CharField(max_length=45, blank=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Registro de auditoría'
        verbose_name_plural = 'Registros de auditoría'

    def __str__(self):
        return f"{self.fecha:%Y-%m-%d %H:%M} · {self.usuario} · {self.accion} ({self.modulo})"
