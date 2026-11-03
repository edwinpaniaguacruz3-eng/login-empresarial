from django import forms
from django.contrib import admin
from django.contrib.auth.hashers import make_password
from .models import Departamento, Empleado, Proveedor


class EmpleadoAdminForm(forms.ModelForm):
    """Formulario del admin que hashea la contraseña al guardarla."""

    class Meta:
        model = Empleado
        fields = '__all__'
        widgets = {
            'password': forms.PasswordInput(render_value=False),
        }

    def clean_password(self):
        password = self.cleaned_data.get('password')
        # Si se deja vacía, se conserva la contraseña actual
        if not password:
            return self.instance.password
        # Si ya tiene formato de hash, se guarda tal cual
        if password.startswith(('pbkdf2_', 'argon2', 'scrypt', 'bcrypt')):
            return password
        return make_password(password)


@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'descripcion', 'activo')
    search_fields = ('nombre',)

    def has_delete_permission(self, request, obj=None):
        """Sin borrado físico: la baja se gestiona desde la app
        (desactivación lógica en departamento_delete)."""
        return False


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'contacto', 'correo', 'telefono', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre', 'contacto', 'correo')

    def has_delete_permission(self, request, obj=None):
        """Sin borrado físico: la baja se gestiona desde la app
        (desactivación lógica en proveedor_delete)."""
        return False


@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    form = EmpleadoAdminForm
    list_display = ('id', 'nombre', 'apellido', 'correo', 'puesto', 'departamento', 'rol', 'activo')
    list_filter = ('departamento', 'rol', 'activo')
    search_fields = ('nombre', 'apellido', 'correo', 'puesto')

    def has_delete_permission(self, request, obj=None):
        """Sin borrado físico: la baja se gestiona desde la app
        (desactivación lógica en empleado_delete)."""
        return False
