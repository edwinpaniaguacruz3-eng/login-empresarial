"""Establece o cambia la contraseña de un empleado (se almacena hasheada)."""
import getpass

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from login.models import Empleado


class Command(BaseCommand):
    help = 'Establece o cambia la contraseña de un empleado'

    def add_arguments(self, parser):
        parser.add_argument('correo', help='Correo electrónico del empleado')
        parser.add_argument(
            '--password',
            help='Contraseña nueva (si se omite, se pedirá de forma oculta)',
        )

    def handle(self, *args, **options):
        correo = options['correo']
        try:
            empleado = Empleado.objects.get(correo=correo)
        except Empleado.DoesNotExist:
            raise CommandError(f'No existe un empleado con el correo "{correo}"')

        password = options['password']
        if not password:
            password = getpass.getpass('Contraseña nueva: ')
            confirmacion = getpass.getpass('Repite la contraseña: ')
            if password != confirmacion:
                raise CommandError('Las contraseñas no coinciden')

        if len(password) < 8:
            raise CommandError('La contraseña debe tener al menos 8 caracteres')

        # Validadores nativos de Django (contraseñas comunes, puramente
        # numéricas, etc.). Los que requieren el usuario se omiten de forma
        # segura porque Empleado no es un auth.User.
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        try:
            validate_password(password, user=None)
        except ValidationError as e:
            raise CommandError('; '.join(e.messages))

        empleado.password = make_password(password)
        empleado.save()

        self.stdout.write(
            self.style.SUCCESS(
                f'Contraseña actualizada correctamente para {empleado.correo}'
            )
        )
