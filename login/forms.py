"""Formularios de la aplicación con validación consistente."""
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Departamento, Empleado, Proveedor, ROL_ADMIN, ROL_EMPLEADO

MIN_LONGITUD_PASSWORD = 8


class DepartamentoForm(forms.ModelForm):
    class Meta:
        model = Departamento
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'autofocus': True}),
            'descripcion': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre', '').strip()
        if not nombre:
            raise ValidationError('El nombre es obligatorio.')
        # Unicidad insensible al formulario (el modelo ya la impone a nivel BD,
        # pero damos un mensaje amigable)
        qs = Departamento.objects.filter(nombre__iexact=nombre)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('Ya existe un departamento con ese nombre.')
        return nombre


class ProveedorForm(forms.ModelForm):
    """Formulario de administración de proveedores (solo administradores).

    - Nombre (razón social) único, insensible a mayúsculas.
    - El estado (activo) se gestiona con desactivar/reactivar,
      igual que en Departamentos: no aparece en el formulario.
    """

    class Meta:
        model = Proveedor
        fields = ['nombre', 'contacto', 'correo', 'telefono', 'direccion']
        widgets = {
            'nombre': forms.TextInput(attrs={'autofocus': True}),
            'direccion': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre', '').strip()
        if not nombre:
            raise ValidationError('El nombre es obligatorio.')
        # Unicidad insensible a mayúsculas (el modelo ya la impone a nivel BD,
        # pero damos un mensaje amigable)
        qs = Proveedor.objects.filter(nombre__iexact=nombre)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('Ya existe un proveedor con ese nombre.')
        return nombre

    def clean_contacto(self):
        contacto = self.cleaned_data.get('contacto') or ''
        return contacto.strip()

    def clean_correo(self):
        correo = self.cleaned_data.get('correo') or ''
        return correo.strip().lower()

    def clean_telefono(self):
        telefono = self.cleaned_data.get('telefono') or ''
        return telefono.strip()


class EmpleadoForm(forms.ModelForm):
    """Formulario de administración de empleados (solo administradores).

    - En creación: la contraseña es obligatoria y se valida con los
      validadores de Django.
    - En edición: vacía = conservar la contraseña actual.
    - No expone el campo `rol`: el rol solo se cambia desde el formulario
      de edición de administradores (empleado_rol_form) o desde makeadmin,
      nunca desde la creación.
    """

    password = forms.CharField(
        label='Contraseña',
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text='Mínimo 8 caracteres. En edición, déjala vacía para conservar la actual.',
    )

    class Meta:
        model = Empleado
        fields = ['nombre', 'apellido', 'correo', 'puesto', 'departamento', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'autofocus': True}),
        }

    def __init__(self, *args, **kwargs):
        self.requerir_password = kwargs.pop('requerir_password', False)
        super().__init__(*args, **kwargs)
        # Nuevas asignaciones solo a departamentos activos; al editar,
        # se conserva el departamento actual aunque esté desactivado
        # (evita reasignaciones involuntarias al editar otros datos).
        departamentos = Departamento.objects.filter(activo=True)
        if self.instance and self.instance.pk and self.instance.departamento_id:
            departamentos = departamentos | Departamento.objects.filter(
                pk=self.instance.departamento_id
            )
        self.fields['departamento'].queryset = departamentos
        if self.requerir_password:
            self.fields['password'].required = True
            self.fields['password'].help_text = (
                'Mínimo 8 caracteres. El empleado usará esta contraseña '
                'para iniciar sesión.'
            )

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre', '').strip()
        if not nombre:
            raise ValidationError('El nombre es obligatorio.')
        return nombre

    def clean_apellido(self):
        apellido = self.cleaned_data.get('apellido', '').strip()
        if not apellido:
            raise ValidationError('El apellido es obligatorio.')
        return apellido

    def clean_correo(self):
        correo = self.cleaned_data.get('correo', '').strip().lower()
        if not correo:
            raise ValidationError('El correo es obligatorio.')
        qs = Empleado.objects.filter(correo__iexact=correo)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('Ya existe un empleado con ese correo.')
        return correo

    def clean_puesto(self):
        puesto = self.cleaned_data.get('puesto', '').strip()
        if not puesto:
            raise ValidationError('El puesto es obligatorio.')
        return puesto

    def clean_password(self):
        password = self.cleaned_data.get('password') or ''
        if not password:
            if self.requerir_password:
                raise ValidationError('La contraseña es obligatoria para crear el empleado.')
            return ''  # conservar la actual
        if len(password) < MIN_LONGITUD_PASSWORD:
            raise ValidationError(
                f'La contraseña debe tener al menos {MIN_LONGITUD_PASSWORD} caracteres.'
            )
        # Validadores nativos de Django (similitud, común, puramente numérica…)
        try:
            validate_password(password, user=None)
        except ValidationError as e:
            raise ValidationError(list(e.messages))
        return password


class EmpleadoRolForm(forms.ModelForm):
    """Asignación de rol y estado (solo administradores, nunca sobre uno mismo
    para ciertas operaciones que se validan en la vista)."""

    class Meta:
        model = Empleado
        fields = ['rol', 'activo']

    def clean_rol(self):
        return self.cleaned_data.get('rol') or ROL_EMPLEADO


class EmpleadoPerfilForm(forms.ModelForm):
    """Edición del perfil propio (datos de identidad)."""

    class Meta:
        model = Empleado
        fields = ['nombre', 'apellido', 'correo']
        widgets = {
            'nombre': forms.TextInput(attrs={'autofocus': True}),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre', '').strip()
        if not nombre:
            raise ValidationError('El nombre es obligatorio.')
        return nombre

    def clean_apellido(self):
        apellido = self.cleaned_data.get('apellido', '').strip()
        if not apellido:
            raise ValidationError('El apellido es obligatorio.')
        return apellido

    def clean_correo(self):
        correo = self.cleaned_data.get('correo', '').strip().lower()
        if not correo:
            raise ValidationError('El correo es obligatorio.')
        qs = Empleado.objects.filter(correo__iexact=correo).exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('Ya existe un empleado con ese correo.')
        return correo


class ContrasenaPropiaForm(forms.Form):
    """Cambio de contraseña del propio usuario (requiere la contraseña actual)."""

    password_actual = forms.CharField(
        label='Contraseña actual',
        widget=forms.PasswordInput,
    )
    password_nueva = forms.CharField(
        label='Contraseña nueva',
        widget=forms.PasswordInput,
        help_text=f'Mínimo {MIN_LONGITUD_PASSWORD} caracteres.',
    )
    password_nueva2 = forms.CharField(
        label='Repite la contraseña nueva',
        widget=forms.PasswordInput,
    )

    def __init__(self, *args, **kwargs):
        self.empleado = kwargs.pop('empleado')
        super().__init__(*args, **kwargs)

    def clean_password_actual(self):
        actual = self.cleaned_data.get('password_actual') or ''
        if not self.empleado.check_password(actual):
            raise ValidationError('La contraseña actual no es correcta.')
        return actual

    def clean_password_nueva(self):
        nueva = self.cleaned_data.get('password_nueva') or ''
        if len(nueva) < MIN_LONGITUD_PASSWORD:
            raise ValidationError(
                f'La contraseña debe tener al menos {MIN_LONGITUD_PASSWORD} caracteres.'
            )
        try:
            validate_password(nueva, user=None)
        except ValidationError as e:
            raise ValidationError(list(e.messages))
        return nueva

    def clean(self):
        cleaned = super().clean()
        nueva = cleaned.get('password_nueva')
        nueva2 = cleaned.get('password_nueva2')
        if nueva and nueva2 and nueva != nueva2:
            self.add_error('password_nueva2', 'Las contraseñas nuevas no coinciden.')
        return cleaned


class ContrasenaAdminForm(forms.Form):
    """Restablecimiento de contraseña de otro empleado (solo administradores)."""

    password_nueva = forms.CharField(
        label='Contraseña nueva',
        widget=forms.PasswordInput,
        help_text=f'Mínimo {MIN_LONGITUD_PASSWORD} caracteres.',
    )
    password_nueva2 = forms.CharField(
        label='Repite la contraseña nueva',
        widget=forms.PasswordInput,
    )

    def clean_password_nueva(self):
        nueva = self.cleaned_data.get('password_nueva') or ''
        if len(nueva) < MIN_LONGITUD_PASSWORD:
            raise ValidationError(
                f'La contraseña debe tener al menos {MIN_LONGITUD_PASSWORD} caracteres.'
            )
        try:
            validate_password(nueva, user=None)
        except ValidationError as e:
            raise ValidationError(list(e.messages))
        return nueva

    def clean(self):
        cleaned = super().clean()
        nueva = cleaned.get('password_nueva')
        nueva2 = cleaned.get('password_nueva2')
        if nueva and nueva2 and nueva != nueva2:
            self.add_error('password_nueva2', 'Las contraseñas no coinciden.')
        return cleaned
