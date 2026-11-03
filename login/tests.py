from io import StringIO

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from .models import Departamento, Empleado, Proveedor, RegistroAuditoria


class LoginTests(TestCase):
    """Pruebas del flujo de login, sesión y dashboard."""

    @classmethod
    def setUpTestData(cls):
        cls.departamento = Departamento.objects.create(nombre='Tecnología')
        cls.empleado = Empleado.objects.create(
            nombre='Prueba',
            apellido='Acceso',
            correo='prueba.acceso@ejemplo.test',
            puesto='Desarrollador',
            departamento=cls.departamento,
            password=make_password('ClaveValida123'),
        )

    def setUp(self):
        # Aislar el contador de intentos de login entre pruebas
        cache.clear()

    # ---------- Formulario ----------

    def test_formulario_login_visible_sin_sesion(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')

    # ---------- Login correcto ----------

    def test_login_correcto_por_correo(self):
        response = self.client.post(reverse('home'), {
            'username': 'prueba.acceso@ejemplo.test',
            'password': 'ClaveValida123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('usuario_id', self.client.session)
        self.assertEqual(self.client.session['usuario_nombre'], 'Prueba Acceso')

    def test_login_correcto_por_nombre(self):
        response = self.client.post(reverse('home'), {
            'username': 'Prueba',
            'password': 'ClaveValida123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('usuario_id', self.client.session)

    # ---------- Login incorrecto ----------

    def test_login_contraseña_incorrecta(self):
        response = self.client.post(reverse('home'), {
            'username': 'prueba.acceso@ejemplo.test',
            'password': 'incorrecta',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('usuario_id', self.client.session)
        self.assertContains(response, 'Credenciales inválidas')

    def test_login_usuario_inexistente(self):
        response = self.client.post(reverse('home'), {
            'username': 'no.existe@ejemplo.test',
            'password': 'cualquiera',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('usuario_id', self.client.session)

    def test_login_empleado_inactivo(self):
        Empleado.objects.filter(pk=self.empleado.pk).update(activo=False)
        response = self.client.post(reverse('home'), {
            'username': 'prueba.acceso@ejemplo.test',
            'password': 'ClaveValida123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('usuario_id', self.client.session)

    def test_login_empleado_sin_contraseña_configurada(self):
        Empleado.objects.filter(pk=self.empleado.pk).update(password='')
        response = self.client.post(reverse('home'), {
            'username': 'prueba.acceso@ejemplo.test',
            'password': 'ClaveValida123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('usuario_id', self.client.session)

    # ---------- Dashboard ----------

    def test_dashboard_muestra_directorio_con_sesion(self):
        self.client.post(reverse('home'), {
            'username': 'prueba.acceso@ejemplo.test',
            'password': 'ClaveValida123',
        })
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Directorio de Empleados')
        self.assertContains(response, 'prueba.acceso@ejemplo.test')
        # La plantilla no debe contener restos de marcado Markdown (corrección M2)
        self.assertNotContains(response, '```')

    def test_buscador_dashboard(self):
        self.client.post(reverse('home'), {
            'username': 'prueba.acceso@ejemplo.test',
            'password': 'ClaveValida123',
        })
        response = self.client.get(reverse('home'), {'q': 'Desarrollador'})
        self.assertContains(response, 'Prueba Acceso')
        response = self.client.get(reverse('home'), {'q': 'zzz-sin-resultados'})
        self.assertContains(response, 'No se encontraron resultados')

    # ---------- Fuerza bruta ----------

    def test_limite_intentos_login(self):
        for _ in range(5):
            self.client.post(reverse('home'), {
                'username': 'prueba.acceso@ejemplo.test',
                'password': 'incorrecta',
            })
        # El 6.º intento, aunque sea con la contraseña correcta, queda bloqueado
        response = self.client.post(reverse('home'), {
            'username': 'prueba.acceso@ejemplo.test',
            'password': 'ClaveValida123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Demasiados intentos fallidos')
        self.assertNotIn('usuario_id', self.client.session)

    # ---------- Cierre de sesión ----------

    def test_logout_requiere_post(self):
        self.client.post(reverse('home'), {
            'username': 'prueba.acceso@ejemplo.test',
            'password': 'ClaveValida123',
        })
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 405)
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('usuario_id', self.client.session)

    # ---------- Modelo ----------

    def test_modelo_set_y_check_password(self):
        empleado = Empleado.objects.get(pk=self.empleado.pk)
        self.assertTrue(empleado.check_password('ClaveValida123'))
        self.assertFalse(empleado.check_password('otra-clave'))
        empleado.set_password('NuevaClave456')
        empleado.save()
        self.assertTrue(
            Empleado.objects.get(pk=self.empleado.pk).check_password('NuevaClave456')
        )
        # El hash nunca es igual a la contraseña en texto plano
        self.assertNotEqual(
            Empleado.objects.get(pk=self.empleado.pk).password,
            'NuevaClave456',
        )


# ============================================================
# Utilidades compartidas
# ============================================================

class AccesoBase(TestCase):
    """Crea un administrador y un empleado para probar permisos."""

    @classmethod
    def setUpTestData(cls):
        cls.departamento = Departamento.objects.create(nombre='Tecnología')
        cls.admin = Empleado.objects.create(
            nombre='Admin',
            apellido='Principal',
            correo='admin@ejemplo.test',
            puesto='Director',
            departamento=cls.departamento,
            rol='admin',
            password=make_password('AdminSeguro123'),
        )
        cls.empleado = Empleado.objects.create(
            nombre='Empleado',
            apellido='Basico',
            correo='empleado@ejemplo.test',
            puesto='Analista',
            departamento=cls.departamento,
            password=make_password('EmpleadoSeguro123'),
        )
        # Departamento sin empleados (para probar su eliminación)
        cls.departamento_vacio = Departamento.objects.create(nombre='Vacío')

    def _login(self, usuario, password):
        return self.client.post(reverse('home'), {
            'username': usuario,
            'password': password,
        })

    def login_admin(self):
        return self._login('admin@ejemplo.test', 'AdminSeguro123')

    def login_empleado(self):
        return self._login('empleado@ejemplo.test', 'EmpleadoSeguro123')


# ============================================================
# Control de acceso por URL
# ============================================================

class AccesoPorURLTests(AccesoBase):
    """Protección de vistas y URLs según el rol."""

    URLS_ADMIN = [
        'empleado_create', 'empleado_update', 'empleado_delete',
        'empleado_rol', 'empleado_contrasena',
        'departamento_create', 'departamento_update', 'departamento_delete',
        'auditoria_list',
    ]

    URLS_TODOS = [
        'home', 'empleado_list', 'empleado_detail',
        'departamento_list', 'departamento_detail',
        'perfil', 'perfil_editar', 'perfil_contrasena',
    ]

    def _urls_con_pk(self, nombre):
        """Resuelve URLs que requieren pk usando el empleado de prueba."""
        if nombre in ('empleado_update', 'empleado_delete', 'empleado_rol',
                      'empleado_contrasena', 'empleado_detail'):
            return reverse(nombre, kwargs={'pk': self.empleado.pk})
        if nombre in ('departamento_update', 'departamento_detail'):
            return reverse(nombre, kwargs={'pk': self.departamento.pk})
        if nombre == 'departamento_delete':
            # Solo los departamentos SIN empleados permiten llegar al delete
            return reverse(nombre, kwargs={'pk': self.departamento_vacio.pk})
        return reverse(nombre)

    def test_urls_administrativas_redirigen_anonymous(self):
        """Sin sesión: las URLs de administración redirigen al login."""
        for nombre in self.URLS_ADMIN:
            response = self.client.get(self._urls_con_pk(nombre))
            self.assertEqual(response.status_code, 302, nombre)
            self.assertIn(reverse('home'), response.url)

    def test_urls_publicas_redirigen_anonymous(self):
        """Sin sesión: el resto de URLs también exigen login."""
        for nombre in self.URLS_TODOS:
            if nombre == 'home':
                continue  # home es la página de login
            response = self.client.get(self._urls_con_pk(nombre))
            self.assertEqual(response.status_code, 302, nombre)

    def test_empleado_bloqueado_en_urls_administrativas(self):
        """Un empleado recibe 403 al acceder directamente a URLs de admin."""
        self.login_empleado()
        for nombre in self.URLS_ADMIN:
            response = self.client.get(self._urls_con_pk(nombre))
            self.assertEqual(response.status_code, 403, nombre)

    def test_empleado_accede_modulos_permitidos(self):
        """Un empleado sí accede a directorio, departamentos y su perfil."""
        self.login_empleado()
        for nombre in self.URLS_TODOS:
            response = self.client.get(self._urls_con_pk(nombre))
            self.assertEqual(response.status_code, 200, nombre)

    def test_admin_accede_todas_las_urls(self):
        """Un administrador accede a todas las URLs."""
        self.login_admin()
        for nombre in self.URLS_ADMIN + self.URLS_TODOS:
            response = self.client.get(self._urls_con_pk(nombre))
            self.assertEqual(response.status_code, 200, nombre)

    def test_sesion_huerfana_se_cierra(self):
        """Si el empleado de la sesión es eliminado, la sesión se invalida."""
        self.login_empleado()
        self.assertIn('usuario_id', self.client.session)
        Empleado.objects.filter(pk=self.empleado.pk).delete()
        response = self.client.get(reverse('empleado_list'))
        self.assertEqual(response.status_code, 302)  # redirige al login
        # Al volver al inicio, la sesión huérfana se cierra por completo
        self.client.get(reverse('home'))
        self.assertNotIn('usuario_id', self.client.session)

    def test_empleado_desactivado_pierde_acceso(self):
        """Un empleado desactivado no puede navegar aunque tenga sesión."""
        self.login_empleado()
        Empleado.objects.filter(pk=self.empleado.pk).update(activo=False)
        response = self.client.get(reverse('empleado_list'))
        self.assertEqual(response.status_code, 302)

    def test_pagina_403_personalizada(self):
        """La respuesta 403 muestra la página de acceso denegado."""
        self.login_empleado()
        response = self.client.get(reverse('empleado_create'))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Acceso denegado', status_code=403)

    def test_url_inexistente_404(self):
        """Una URL inexistente muestra la página 404 personalizada."""
        response = self.client.get('/url/que/no/existe/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'Página no encontrada', status_code=404)


# ============================================================
# CRUD de Empleados
# ============================================================

class CRUDEmpleadoTests(AccesoBase):

    def test_listar_empleados(self):
        self.login_admin()
        response = self.client.get(reverse('empleado_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Empleado Basico')
        self.assertContains(response, 'Admin Principal')

    def test_detalle_empleado(self):
        self.login_admin()
        response = self.client.get(
            reverse('empleado_detail', kwargs={'pk': self.empleado.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'empleado@ejemplo.test')
        self.assertContains(response, 'Analista')

    def test_detalle_empleado_inexistente_404(self):
        self.login_admin()
        response = self.client.get(
            reverse('empleado_detail', kwargs={'pk': 99999})
        )
        self.assertEqual(response.status_code, 404)

    def test_crear_empleado(self):
        self.login_admin()
        response = self.client.post(reverse('empleado_create'), {
            'nombre': 'Nuevo',
            'apellido': 'Empleado',
            'correo': 'nuevo@ejemplo.test',
            'puesto': 'Técnico',
            'departamento': self.departamento.pk,
            'activo': True,
            'password': 'NuevoSeguro123',
        })
        self.assertEqual(response.status_code, 302)
        nuevo = Empleado.objects.get(correo='nuevo@ejemplo.test')
        # La contraseña se almacena hasheada, nunca en texto plano
        self.assertNotEqual(nuevo.password, 'NuevoSeguro123')
        self.assertTrue(nuevo.check_password('NuevoSeguro123'))
        self.assertEqual(nuevo.rol, 'empleado')  # mínimo privilegio

    def test_crear_empleado_valida_datos(self):
        self.login_admin()
        # Faltan campos obligatorios (mensaje nativo de Django)
        response = self.client.post(reverse('empleado_create'), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Este campo es obligatorio')
        # Correo duplicado
        response = self.client.post(reverse('empleado_create'), {
            'nombre': 'Copia', 'apellido': 'Duplicada',
            'correo': 'empleado@ejemplo.test', 'puesto': 'X',
            'departamento': self.departamento.pk,
            'password': 'OtroSeguro123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ya existe un empleado con ese correo')
        # Contraseña corta
        response = self.client.post(reverse('empleado_create'), {
            'nombre': 'Corta', 'apellido': 'Clave',
            'correo': 'corta@ejemplo.test', 'puesto': 'X',
            'departamento': self.departamento.pk,
            'password': '1234567',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'al menos 8 caracteres')

    def test_editar_empleado(self):
        self.login_admin()
        response = self.client.post(
            reverse('empleado_update', kwargs={'pk': self.empleado.pk}),
            {
                'nombre': 'Empleado', 'apellido': 'Modificado',
                'correo': 'empleado@ejemplo.test', 'puesto': 'Analista Senior',
                'departamento': self.departamento.pk, 'activo': True,
                'password': '',  # vacía: conserva la actual
            }
        )
        self.assertEqual(response.status_code, 302)
        self.empleado.refresh_from_db()
        self.assertEqual(self.empleado.apellido, 'Modificado')
        self.assertEqual(self.empleado.puesto, 'Analista Senior')
        # La contraseña sigue funcionando
        self.assertTrue(self.empleado.check_password('EmpleadoSeguro123'))

    def test_editar_empleado_cambia_contraseña(self):
        self.login_admin()
        response = self.client.post(
            reverse('empleado_update', kwargs={'pk': self.empleado.pk}),
            {
                'nombre': 'Empleado', 'apellido': 'Basico',
                'correo': 'empleado@ejemplo.test', 'puesto': 'Analista',
                'departamento': self.departamento.pk, 'activo': True,
                'password': 'OtraClaveSegura456',
            }
        )
        self.assertEqual(response.status_code, 302)
        self.empleado.refresh_from_db()
        self.assertTrue(self.empleado.check_password('OtraClaveSegura456'))

    def test_admin_no_puede_desactivarse_a_si_mismo(self):
        self.login_admin()
        response = self.client.post(
            reverse('empleado_update', kwargs={'pk': self.admin.pk}),
            {
                'nombre': 'Admin', 'apellido': 'Principal',
                'correo': 'admin@ejemplo.test', 'puesto': 'Director',
                'departamento': self.departamento.pk, 'activo': False,
                'password': '',
            }
        )
        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.activo)  # sigue activo
        self.assertContains(response, 'No puedes desactivar tu propia cuenta')

    def test_admin_no_puede_eliminarse_a_si_mismo(self):
        self.login_admin()
        response = self.client.post(
            reverse('empleado_delete', kwargs={'pk': self.admin.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Empleado.objects.filter(pk=self.admin.pk).exists())

    def test_desactivar_empleado(self):
        self.login_admin()
        # El admin (activo) sigue existiendo, así que el empleado puede desactivarse
        response = self.client.post(
            reverse('empleado_delete', kwargs={'pk': self.empleado.pk})
        )
        self.assertEqual(response.status_code, 302)
        # Desactivación lógica: el registro se conserva con sus datos
        self.assertTrue(Empleado.objects.filter(pk=self.empleado.pk).exists())
        self.empleado.refresh_from_db()
        self.assertFalse(self.empleado.activo)
        self.assertEqual(self.empleado.correo, 'empleado@ejemplo.test')

    def test_otro_admin_puede_desactivar_admin(self):
        """Un administrador puede desactivar a otro administrador (queda él activo)."""
        otro_admin = Empleado.objects.create(
            nombre='Otro', apellido='Admin', correo='otro.admin@ejemplo.test',
            puesto='X', departamento=self.departamento, rol='admin',
            password=make_password('OtroAdmin123'),
        )
        self.client.post(reverse('logout'))
        self._login('otro.admin@ejemplo.test', 'OtroAdmin123')
        response = self.client.post(
            reverse('empleado_delete', kwargs={'pk': self.admin.pk})
        )
        self.assertEqual(response.status_code, 302)
        # El registro del admin desactivado se conserva
        self.assertTrue(Empleado.objects.filter(pk=self.admin.pk).exists())
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.activo)
        self.assertTrue(
            Empleado.objects.filter(pk=otro_admin.pk, rol='admin', activo=True).exists()
        )

    def test_empleado_no_puede_crear_empleados(self):
        self.login_empleado()
        response = self.client.post(reverse('empleado_create'), {
            'nombre': 'Intruso', 'apellido': 'X',
            'correo': 'intruso@ejemplo.test', 'puesto': 'X',
            'departamento': self.departamento.pk, 'password': 'Intruso12345',
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Empleado.objects.filter(correo='intruso@ejemplo.test').exists())

    def test_empleado_no_puede_editar_ni_eliminar(self):
        self.login_empleado()
        response = self.client.post(
            reverse('empleado_update', kwargs={'pk': self.empleado.pk}),
            {'nombre': 'Hack', 'apellido': 'X', 'correo': 'empleado@ejemplo.test',
             'puesto': 'X', 'departamento': self.departamento.pk,
             'activo': True, 'password': ''}
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('empleado_delete', kwargs={'pk': self.admin.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Empleado.objects.filter(pk=self.admin.pk).exists())

    # ---------- Rol y estado ----------

    def test_admin_cambia_rol_y_estado(self):
        self.login_admin()
        response = self.client.post(
            reverse('empleado_rol', kwargs={'pk': self.empleado.pk}),
            {'rol': 'admin', 'activo': True}
        )
        self.assertEqual(response.status_code, 302)
        self.empleado.refresh_from_db()
        self.assertEqual(self.empleado.rol, 'admin')

    def test_admin_no_puede_cambiar_su_propio_rol(self):
        self.login_admin()
        response = self.client.post(
            reverse('empleado_rol', kwargs={'pk': self.admin.pk}),
            {'rol': 'empleado', 'activo': True}
        )
        self.assertEqual(response.status_code, 302)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.rol, 'admin')  # no cambió

    def test_admin_puede_quitar_rol_a_otro_admin(self):
        """Un admin puede quitar el rol a otro admin (él sigue siendo admin)."""
        otro_admin = Empleado.objects.create(
            nombre='Otro', apellido='Admin', correo='otro.admin@ejemplo.test',
            puesto='X', departamento=self.departamento, rol='admin',
            password=make_password('OtroAdmin123'),
        )
        self.client.post(reverse('logout'))
        self._login('otro.admin@ejemplo.test', 'OtroAdmin123')
        response = self.client.post(
            reverse('empleado_rol', kwargs={'pk': self.admin.pk}),
            {'rol': 'empleado', 'activo': True}
        )
        self.assertEqual(response.status_code, 302)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.rol, 'empleado')
        otro_admin.refresh_from_db()
        self.assertEqual(otro_admin.rol, 'admin')

    # ---------- Restablecimiento de contraseña por admin ----------

    def test_admin_restablece_contraseña(self):
        self.login_admin()
        response = self.client.post(
            reverse('empleado_contrasena', kwargs={'pk': self.empleado.pk}),
            {'password_nueva': 'Restablecida123', 'password_nueva2': 'Restablecida123'}
        )
        self.assertEqual(response.status_code, 302)
        self.empleado.refresh_from_db()
        self.assertTrue(self.empleado.check_password('Restablecida123'))

    def test_admin_restablece_contraseña_no_coincide(self):
        self.login_admin()
        response = self.client.post(
            reverse('empleado_contrasena', kwargs={'pk': self.empleado.pk}),
            {'password_nueva': 'Restablecida123', 'password_nueva2': 'OtraDistinta456'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no coinciden')
        self.empleado.refresh_from_db()
        self.assertTrue(self.empleado.check_password('EmpleadoSeguro123'))

    # ---------- Búsqueda y paginación ----------

    def test_busqueda_y_paginacion_empleados(self):
        self.login_admin()
        for i in range(12):
            Empleado.objects.create(
                nombre=f'Paginado{i}', apellido='Prueba',
                correo=f'pag{i}@ejemplo.test', puesto='X',
                departamento=self.departamento,
            )
        response = self.client.get(reverse('empleado_list'))
        self.assertContains(response, 'Página 1 de 2')
        response = self.client.get(reverse('empleado_list') + '?page=2')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Página 2 de 2')
        response = self.client.get(reverse('empleado_list'), {'q': 'Paginado3'})
        self.assertContains(response, 'Paginado3')
        self.assertContains(response, '1 registro en total.')


# ============================================================
# CRUD de Departamentos
# ============================================================

class CRUDDepartamentoTests(AccesoBase):

    def test_listar_departamentos(self):
        self.login_empleado()
        response = self.client.get(reverse('departamento_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tecnología')

    def test_detalle_departamento(self):
        self.login_empleado()
        response = self.client.get(
            reverse('departamento_detail', kwargs={'pk': self.departamento.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tecnología')
        self.assertContains(response, 'Empleado Basico')

    def test_crear_departamento(self):
        self.login_admin()
        response = self.client.post(reverse('departamento_create'), {
            'nombre': 'Marketing', 'descripcion': 'Área de marketing'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Departamento.objects.filter(nombre='Marketing').exists())

    def test_crear_departamento_duplicado(self):
        self.login_admin()
        response = self.client.post(reverse('departamento_create'), {
            'nombre': 'Tecnología', 'descripcion': ''
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ya existe un departamento con ese nombre')

    def test_editar_departamento(self):
        self.login_admin()
        response = self.client.post(
            reverse('departamento_update', kwargs={'pk': self.departamento.pk}),
            {'nombre': 'Tecnología', 'descripcion': 'Nueva descripción'}
        )
        self.assertEqual(response.status_code, 302)
        self.departamento.refresh_from_db()
        self.assertEqual(self.departamento.descripcion, 'Nueva descripción')

    def test_desactivar_departamento_sin_empleados(self):
        self.login_admin()
        # departamento_vacio no tiene empleados (creado en setUpTestData)
        response = self.client.post(
            reverse('departamento_delete', kwargs={'pk': self.departamento_vacio.pk})
        )
        self.assertEqual(response.status_code, 302)
        # Desactivación lógica: el registro se conserva
        self.assertTrue(Departamento.objects.filter(pk=self.departamento_vacio.pk).exists())
        self.departamento_vacio.refresh_from_db()
        self.assertFalse(self.departamento_vacio.activo)

    def test_desactivar_departamento_con_empleados(self):
        """La desactivación lógica no borra en cascada: se conservan los empleados."""
        self.login_admin()
        response = self.client.post(
            reverse('departamento_delete', kwargs={'pk': self.departamento.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Departamento.objects.filter(pk=self.departamento.pk).exists())
        self.departamento.refresh_from_db()
        self.assertFalse(self.departamento.activo)
        # Los empleados asignados se conservan intactos
        self.empleado.refresh_from_db()
        self.assertEqual(self.empleado.departamento, self.departamento)
        self.assertContains(
            self.client.get(reverse('departamento_detail',
                                    kwargs={'pk': self.departamento.pk})),
            'Tecnología'
        )

    def test_empleado_no_puede_gestionar_departamentos(self):
        self.login_empleado()
        for nombre in ('departamento_create',):
            response = self.client.post(reverse(nombre), {
                'nombre': 'Intruso', 'descripcion': ''
            })
            self.assertEqual(response.status_code, 403, nombre)
        self.assertFalse(Departamento.objects.filter(nombre='Intruso').exists())
        response = self.client.post(
            reverse('departamento_delete', kwargs={'pk': self.departamento.pk})
        )
        self.assertEqual(response.status_code, 403)


# ============================================================
# Desactivación lógica
# ============================================================

class DesactivacionLogicaTests(AccesoBase):
    """Verifica que las bajas son lógicas: nada se borra físicamente."""

    def test_desactivar_empleado_conserva_datos_y_relaciones(self):
        self.login_admin()
        self.client.post(reverse('empleado_delete', kwargs={'pk': self.empleado.pk}))
        empleado = Empleado.objects.get(pk=self.empleado.pk)
        self.assertFalse(empleado.activo)
        self.assertEqual(empleado.correo, 'empleado@ejemplo.test')
        self.assertEqual(empleado.departamento, self.departamento)

    def test_listado_oculta_inactivos_y_permite_consultarlos(self):
        self.login_admin()
        self.client.post(reverse('empleado_delete', kwargs={'pk': self.empleado.pk}))
        # Listado operativo: solo activos (se comprueba por correo:
        # el mensaje de confirmación menciona el nombre del empleado)
        response = self.client.get(reverse('empleado_list'))
        self.assertNotContains(response, 'empleado@ejemplo.test')
        # Consulta histórica: inactivos
        response = self.client.get(reverse('empleado_list'), {'estado': 'inactivos'})
        self.assertContains(response, 'empleado@ejemplo.test')
        # Todos
        response = self.client.get(reverse('empleado_list'), {'estado': 'todos'})
        self.assertContains(response, 'empleado@ejemplo.test')

    def test_detalle_empleado_inactivo_accesible(self):
        self.login_admin()
        self.client.post(reverse('empleado_delete', kwargs={'pk': self.empleado.pk}))
        response = self.client.get(
            reverse('empleado_detail', kwargs={'pk': self.empleado.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'empleado@ejemplo.test')

    def test_reactivar_empleado_conserva_pk(self):
        self.login_admin()
        self.client.post(reverse('empleado_delete', kwargs={'pk': self.empleado.pk}))
        response = self.client.post(
            reverse('empleado_rol', kwargs={'pk': self.empleado.pk}),
            {'rol': 'empleado', 'activo': True}
        )
        self.assertEqual(response.status_code, 302)
        empleado = Empleado.objects.get(pk=self.empleado.pk)
        self.assertTrue(empleado.activo)
        self.assertEqual(empleado.correo, 'empleado@ejemplo.test')

    def test_desactivar_departamento_conserva_datos(self):
        self.login_admin()
        self.client.post(
            reverse('departamento_delete', kwargs={'pk': self.departamento_vacio.pk})
        )
        departamento = Departamento.objects.get(pk=self.departamento_vacio.pk)
        self.assertFalse(departamento.activo)
        self.assertEqual(departamento.nombre, 'Vacío')

    def test_reactivar_departamento_conserva_pk_y_relaciones(self):
        self.login_admin()
        self.client.post(
            reverse('departamento_delete', kwargs={'pk': self.departamento_vacio.pk})
        )
        response = self.client.post(
            reverse('departamento_reactivar', kwargs={'pk': self.departamento_vacio.pk})
        )
        self.assertEqual(response.status_code, 302)
        departamento = Departamento.objects.get(pk=self.departamento_vacio.pk)
        self.assertTrue(departamento.activo)
        self.assertEqual(departamento.nombre, 'Vacío')

    def test_reactivar_departamento_requiere_admin(self):
        """Solo administradores pueden reactivar; el empleado recibe 403."""
        self.login_empleado()
        response = self.client.post(
            reverse('departamento_reactivar', kwargs={'pk': self.departamento_vacio.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.departamento_vacio.refresh_from_db()
        self.assertTrue(self.departamento_vacio.activo)

    def test_reactivar_departamento_sin_sesion_redirige(self):
        response = self.client.post(
            reverse('departamento_reactivar', kwargs={'pk': self.departamento_vacio.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_formulario_empleado_solo_ofrece_departamentos_activos(self):
        from .forms import EmpleadoForm
        self.login_admin()
        self.client.post(
            reverse('departamento_delete', kwargs={'pk': self.departamento_vacio.pk})
        )
        form = EmpleadoForm()
        qs = form.fields['departamento'].queryset
        self.assertIn(self.departamento, qs)
        self.assertNotIn(self.departamento_vacio, qs)

    def test_admin_sin_permiso_de_borrado_fisico(self):
        """El panel /admin/ ya no ofrece borrado físico de entidades de negocio."""
        from django.contrib import admin as admin_site
        from .admin import DepartamentoAdmin, EmpleadoAdmin
        self.assertFalse(
            DepartamentoAdmin(Departamento, admin_site.site).has_delete_permission(None)
        )
        self.assertFalse(
            EmpleadoAdmin(Empleado, admin_site.site).has_delete_permission(None)
        )

    def test_auditoria_registra_desactivacion_y_reactivacion(self):
        self.login_admin()
        self.client.post(reverse('empleado_delete', kwargs={'pk': self.empleado.pk}))
        self.assertTrue(RegistroAuditoria.objects.filter(
            modulo='empleado', accion='desactivar'
        ).exists())
        self.client.post(
            reverse('empleado_rol', kwargs={'pk': self.empleado.pk}),
            {'rol': 'empleado', 'activo': True}
        )
        self.assertTrue(RegistroAuditoria.objects.filter(
            modulo='empleado', accion='reactivar'
        ).exists())


# ============================================================
# Perfil propio
# ============================================================

class PerfilTests(AccesoBase):

    def test_ver_perfil(self):
        self.login_empleado()
        response = self.client.get(reverse('perfil'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Empleado Basico')

    def test_editar_perfil(self):
        self.login_empleado()
        response = self.client.post(reverse('perfil_editar'), {
            'nombre': 'NuevoNombre', 'apellido': 'Basico',
            'correo': 'nuevo.correo@ejemplo.test'
        })
        self.assertEqual(response.status_code, 302)
        self.empleado.refresh_from_db()
        self.assertEqual(self.empleado.nombre, 'NuevoNombre')
        self.assertEqual(self.empleado.correo, 'nuevo.correo@ejemplo.test')
        # La sesión se mantiene sincronizada
        self.assertEqual(
            self.client.session['usuario_nombre'], 'NuevoNombre Basico'
        )

    def test_editar_perfil_valida_correo_duplicado(self):
        self.login_admin()
        # El admin intenta usar el correo del empleado (otro usuario)
        response = self.client.post(reverse('perfil_editar'), {
            'nombre': 'Admin', 'apellido': 'Principal',
            'correo': 'empleado@ejemplo.test'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ya existe un empleado con ese correo')

    def test_cambiar_contraseña_propia(self):
        self.login_empleado()
        response = self.client.post(reverse('perfil_contrasena'), {
            'password_actual': 'EmpleadoSeguro123',
            'password_nueva': 'MiNuevaClave789',
            'password_nueva2': 'MiNuevaClave789',
        })
        self.assertEqual(response.status_code, 302)
        self.empleado.refresh_from_db()
        self.assertTrue(self.empleado.check_password('MiNuevaClave789'))

    def test_cambiar_contraseña_con_actual_incorrecta(self):
        self.login_empleado()
        response = self.client.post(reverse('perfil_contrasena'), {
            'password_actual': 'incorrecta',
            'password_nueva': 'MiNuevaClave789',
            'password_nueva2': 'MiNuevaClave789',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'contraseña actual no es correcta')
        self.empleado.refresh_from_db()
        self.assertTrue(self.empleado.check_password('EmpleadoSeguro123'))

    def test_cambiar_contraseña_no_coincide(self):
        self.login_empleado()
        response = self.client.post(reverse('perfil_contrasena'), {
            'password_actual': 'EmpleadoSeguro123',
            'password_nueva': 'MiNuevaClave789',
            'password_nueva2': 'OtraClave999',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no coinciden')
        self.empleado.refresh_from_db()
        self.assertTrue(self.empleado.check_password('EmpleadoSeguro123'))


# ============================================================
# Auditoría
# ============================================================

class AuditoriaTests(AccesoBase):

    def test_se_registra_creacion_de_empleado(self):
        self.login_admin()
        self.client.post(reverse('empleado_create'), {
            'nombre': 'Auditar', 'apellido': 'Creacion',
            'correo': 'auditar@ejemplo.test', 'puesto': 'X',
            'departamento': self.departamento.pk, 'password': 'AuditarSeguro123',
        })
        self.assertTrue(RegistroAuditoria.objects.filter(
            modulo='empleado', accion='crear'
        ).exists())
        registro = RegistroAuditoria.objects.filter(accion='crear').first()
        self.assertEqual(registro.usuario, 'Admin Principal')

    def test_se_registra_login_y_logout(self):
        self.login_empleado()
        self.assertTrue(RegistroAuditoria.objects.filter(
            modulo='sesion', accion='login_ok'
        ).exists())
        self.client.post(reverse('logout'))
        self.assertTrue(RegistroAuditoria.objects.filter(
            modulo='sesion', accion='logout'
        ).exists())

    def test_empleado_no_ve_auditoria(self):
        self.login_empleado()
        response = self.client.get(reverse('auditoria_list'))
        self.assertEqual(response.status_code, 403)

    def test_auditoria_con_filtros(self):
        self.login_admin()
        self.client.post(reverse('empleado_create'), {
            'nombre': 'Auditar', 'apellido': 'Creacion',
            'correo': 'auditar2@ejemplo.test', 'puesto': 'X',
            'departamento': self.departamento.pk, 'password': 'AuditarSeguro123',
        })
        response = self.client.get(reverse('auditoria_list'), {'modulo': 'empleado'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Creación de registro')


# ============================================================
# Seguridad adicional
# ============================================================

class SeguridadTests(AccesoBase):

    def _cliente_csrf(self):
        """Cliente que exige CSRF y ya tiene sesión de admin."""
        cliente = Client(enforce_csrf_checks=True)
        cliente.get(reverse('home'))  # obtiene la cookie csrftoken
        token = cliente.cookies['csrftoken'].value
        response = cliente.post(reverse('home'), {
            'username': 'admin@ejemplo.test', 'password': 'AdminSeguro123',
            'csrfmiddlewaretoken': token,
        })
        self.assertEqual(response.status_code, 302)
        return cliente

    def test_csrf_protegido_en_login(self):
        """Sin token CSRF, el POST de login se rechaza (403)."""
        cliente = Client(enforce_csrf_checks=True)
        response = cliente.post(reverse('home'), {
            'username': 'admin@ejemplo.test', 'password': 'AdminSeguro123',
        })
        self.assertEqual(response.status_code, 403)

    def test_csrf_protegido_en_crud(self):
        """Sin token CSRF, los POST de creación se rechazan (403)."""
        cliente = self._cliente_csrf()
        response = cliente.post(reverse('departamento_create'), {
            'nombre': 'SinCSRF', 'descripcion': ''
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Departamento.objects.filter(nombre='SinCSRF').exists())

    def test_logout_con_csrf(self):
        """El logout sin token CSRF se rechaza."""
        cliente = self._cliente_csrf()
        response = cliente.post(reverse('logout'))
        self.assertEqual(response.status_code, 403)
        # La sesión sigue activa
        self.assertIn('usuario_id', cliente.session)

    def test_hash_no_es_texto_plano_en_creacion(self):
        self.login_admin()
        self.client.post(reverse('empleado_create'), {
            'nombre': 'Hash', 'apellido': 'Prueba',
            'correo': 'hash@ejemplo.test', 'puesto': 'X',
            'departamento': self.departamento.pk, 'password': 'HashSeguro123',
        })
        creado = Empleado.objects.get(correo='hash@ejemplo.test')
        self.assertTrue(creado.password.startswith('pbkdf2_'))

    def test_menu_sin_opciones_admin_para_empleado(self):
        """El sidebar del empleado no muestra enlaces de administración."""
        self.login_empleado()
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, 'Nuevo empleado')
        self.assertNotContains(response, 'Auditoría')
        self.assertContains(response, 'Mi perfil')

    def test_menu_con_opciones_admin(self):
        """El sidebar del administrador muestra las secciones de gestión."""
        self.login_admin()
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Nuevo empleado')
        self.assertContains(response, 'Auditoría')


# ============================================================
# Migraciones
# ============================================================

class MigracionesTests(TestCase):

    def test_sin_cambios_pendientes_en_modelos(self):
        """Los modelos y las migraciones están sincronizados."""
        out = StringIO()
        call_command('makemigrations', 'login', '--check', '--dry-run', stdout=out)
        self.assertIn('No changes detected', out.getvalue())

    def test_migraciones_aplicables_en_orden(self):
        """El grafo de migraciones es consistente (sin dependencias rotas)."""
        out = StringIO()
        call_command('showmigrations', 'login', stdout=out)
        salida = out.getvalue()
        self.assertIn('0001_initial', salida)
        self.assertIn('0002_empleado_password', salida)
        self.assertIn('0003_', salida)


# ============================================================
# CRUD de Proveedores
# ============================================================

class CRUDProveedorTests(AccesoBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.proveedor = Proveedor.objects.create(
            nombre='Suministros del Norte',
            contacto='Ana Torres',
            correo='ana@suministros.test',
            telefono='555-0100',
            direccion='Av. Principal 123',
        )

    def test_listar_proveedores(self):
        self.login_empleado()
        response = self.client.get(reverse('proveedor_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Suministros del Norte')

    def test_detalle_proveedor(self):
        self.login_empleado()
        response = self.client.get(
            reverse('proveedor_detail', kwargs={'pk': self.proveedor.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Suministros del Norte')
        self.assertContains(response, 'ana@suministros.test')
        self.assertContains(response, '555-0100')

    def test_detalle_proveedor_inexistente_404(self):
        self.login_admin()
        response = self.client.get(
            reverse('proveedor_detail', kwargs={'pk': 99999})
        )
        self.assertEqual(response.status_code, 404)

    def test_crear_proveedor(self):
        self.login_admin()
        response = self.client.post(reverse('proveedor_create'), {
            'nombre': 'Papelería Central',
            'contacto': 'Luis Gómez',
            'correo': 'luis@papeleria.test',
            'telefono': '555-0200',
            'direccion': 'Calle 2',
        })
        self.assertEqual(response.status_code, 302)
        proveedor = Proveedor.objects.get(nombre='Papelería Central')
        self.assertTrue(proveedor.activo)
        self.assertEqual(proveedor.contacto, 'Luis Gómez')
        self.assertEqual(proveedor.telefono, '555-0200')

    def test_crear_proveedor_duplicado(self):
        self.login_admin()
        response = self.client.post(reverse('proveedor_create'), {
            'nombre': 'Suministros del Norte',
            'contacto': '', 'correo': '', 'telefono': '', 'direccion': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ya existe un proveedor con ese nombre')

    def test_crear_proveedor_duplicado_insensible_mayusculas(self):
        self.login_admin()
        response = self.client.post(reverse('proveedor_create'), {
            'nombre': 'SUMINISTROS DEL NORTE',
            'contacto': '', 'correo': '', 'telefono': '', 'direccion': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ya existe un proveedor con ese nombre')

    def test_crear_proveedor_valida_datos(self):
        self.login_admin()
        # Faltan campos obligatorios (mensaje nativo de Django)
        response = self.client.post(reverse('proveedor_create'), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Este campo es obligatorio')
        # No se creó nada
        self.assertFalse(Proveedor.objects.filter(nombre='').exists())

    def test_editar_proveedor(self):
        self.login_admin()
        response = self.client.post(
            reverse('proveedor_update', kwargs={'pk': self.proveedor.pk}),
            {
                'nombre': 'Suministros del Norte',
                'contacto': 'Ana Torres Ruiz',
                'correo': 'ana.ruiz@suministros.test',
                'telefono': '555-0199',
                'direccion': 'Av. Principal 456',
            }
        )
        self.assertEqual(response.status_code, 302)
        self.proveedor.refresh_from_db()
        self.assertEqual(self.proveedor.contacto, 'Ana Torres Ruiz')
        self.assertEqual(self.proveedor.telefono, '555-0199')
        self.assertEqual(self.proveedor.direccion, 'Av. Principal 456')

    def test_desactivar_proveedor(self):
        self.login_admin()
        response = self.client.post(
            reverse('proveedor_delete', kwargs={'pk': self.proveedor.pk})
        )
        self.assertEqual(response.status_code, 302)
        # Desactivación lógica: el registro se conserva con sus datos
        self.assertTrue(Proveedor.objects.filter(pk=self.proveedor.pk).exists())
        self.proveedor.refresh_from_db()
        self.assertFalse(self.proveedor.activo)
        self.assertEqual(self.proveedor.nombre, 'Suministros del Norte')

    def test_desactivar_proveedor_idempotente(self):
        self.login_admin()
        self.client.post(
            reverse('proveedor_delete', kwargs={'pk': self.proveedor.pk})
        )
        response = self.client.post(
            reverse('proveedor_delete', kwargs={'pk': self.proveedor.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.proveedor.refresh_from_db()
        self.assertFalse(self.proveedor.activo)

    def test_reactivar_proveedor(self):
        self.login_admin()
        self.client.post(
            reverse('proveedor_delete', kwargs={'pk': self.proveedor.pk})
        )
        response = self.client.post(
            reverse('proveedor_reactivar', kwargs={'pk': self.proveedor.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.proveedor.refresh_from_db()
        self.assertTrue(self.proveedor.activo)
        # Misma PK y datos
        self.assertEqual(self.proveedor.nombre, 'Suministros del Norte')

    def test_reactivar_proveedor_requiere_admin(self):
        self.login_empleado()
        response = self.client.post(
            reverse('proveedor_reactivar', kwargs={'pk': self.proveedor.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.proveedor.refresh_from_db()
        self.assertTrue(self.proveedor.activo)

    def test_reactivar_proveedor_solo_post(self):
        self.login_admin()
        response = self.client.get(
            reverse('proveedor_reactivar', kwargs={'pk': self.proveedor.pk})
        )
        self.assertEqual(response.status_code, 405)

    def test_busqueda_proveedores(self):
        self.login_empleado()
        response = self.client.get(reverse('proveedor_list'), {'q': 'Suministros'})
        self.assertContains(response, 'Suministros del Norte')
        response = self.client.get(reverse('proveedor_list'), {'q': 'Ana Torres'})
        self.assertContains(response, 'Suministros del Norte')
        response = self.client.get(reverse('proveedor_list'), {'q': 'zzz-sin-resultados'})
        self.assertContains(response, 'No se encontraron resultados')

    def test_filtro_estado_proveedores(self):
        self.login_admin()
        self.client.post(
            reverse('proveedor_delete', kwargs={'pk': self.proveedor.pk})
        )
        # Listado operativo: solo activos (se comprueba por correo:
        # el mensaje de confirmación menciona el nombre del proveedor)
        response = self.client.get(reverse('proveedor_list'))
        self.assertNotContains(response, 'ana@suministros.test')
        # Consulta histórica: inactivos
        response = self.client.get(reverse('proveedor_list'), {'estado': 'inactivos'})
        self.assertContains(response, 'ana@suministros.test')
        # Todos
        response = self.client.get(reverse('proveedor_list'), {'estado': 'todos'})
        self.assertContains(response, 'ana@suministros.test')

    def test_empleado_no_puede_gestionar_proveedores(self):
        self.login_empleado()
        response = self.client.post(reverse('proveedor_create'), {
            'nombre': 'Intruso', 'contacto': '', 'correo': '',
            'telefono': '', 'direccion': '',
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Proveedor.objects.filter(nombre='Intruso').exists())
        response = self.client.post(
            reverse('proveedor_delete', kwargs={'pk': self.proveedor.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.proveedor.refresh_from_db()
        self.assertTrue(self.proveedor.activo)

    def test_anonymous_redirige_proveedores(self):
        response = self.client.get(reverse('proveedor_list'))
        self.assertEqual(response.status_code, 302)
        response = self.client.get(
            reverse('proveedor_detail', kwargs={'pk': self.proveedor.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_admin_sin_permiso_de_borrado_fisico_proveedor(self):
        """El panel /admin/ no ofrece borrado físico de proveedores."""
        from django.contrib import admin as admin_site
        from .admin import ProveedorAdmin
        self.assertFalse(
            ProveedorAdmin(Proveedor, admin_site.site).has_delete_permission(None)
        )


# ============================================================
# Roles y permisos (consulta)
# ============================================================

class RolesPermisosTests(AccesoBase):

    def test_roles_list_admin(self):
        self.login_admin()
        response = self.client.get(reverse('roles_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Roles y permisos')
        self.assertContains(response, 'Matriz de permisos')
        self.assertContains(response, 'Administrador')
        self.assertContains(response, 'Empleado')

    def test_roles_list_empleado_403(self):
        self.login_empleado()
        response = self.client.get(reverse('roles_list'))
        self.assertEqual(response.status_code, 403)

    def test_roles_list_anonymous_302(self):
        response = self.client.get(reverse('roles_list'))
        self.assertEqual(response.status_code, 302)

    def test_matriz_incluye_modulos(self):
        self.login_admin()
        response = self.client.get(reverse('roles_list'))
        for modulo in (
            'Empleados (usuarios)',
            'Departamentos (sucursales)',
            'Proveedores',
            'Auditoría',
        ):
            self.assertContains(response, modulo)

    def test_asignacion_rol_sigue_en_ficha_empleado(self):
        """La asignación/retirada de permisos se realiza desde la
        ficha del empleado (mecanismo existente)."""
        self.login_admin()
        response = self.client.get(
            reverse('empleado_rol', kwargs={'pk': self.empleado.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Asignación de permisos')
