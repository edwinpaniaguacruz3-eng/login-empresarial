"""Promueve un empleado a administrador (bootstrap de roles)."""
from django.core.management.base import BaseCommand, CommandError

from login.models import Empleado


class Command(BaseCommand):
    help = 'Asigna el rol de administrador a un empleado existente'

    def add_arguments(self, parser):
        parser.add_argument('correo', help='Correo electrónico del empleado')

    def handle(self, *args, **options):
        correo = options['correo'].strip().lower()
        try:
            empleado = Empleado.objects.get(correo__iexact=correo)
        except Empleado.DoesNotExist:
            raise CommandError(f'No existe un empleado con el correo "{correo}"')

        if empleado.rol == 'admin':
            self.stdout.write(
                self.style.WARNING(f'{empleado.correo} ya es administrador.')
            )
            return

        if not empleado.activo:
            self.stdout.write(
                self.style.WARNING(
                    f'Advertencia: {empleado.correo} está INACTIVO y no '
                    'podrá iniciar sesión hasta que se active.'
                )
            )

        empleado.rol = 'admin'
        empleado.save()

        self.stdout.write(
            self.style.SUCCESS(
                f'Correcto: {empleado.correo} ahora es ADMINISTRADOR.'
            )
        )
