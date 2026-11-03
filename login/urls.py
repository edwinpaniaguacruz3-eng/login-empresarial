from django.urls import path

from . import views

urlpatterns = [
    # Público / inicio de sesión
    path('', views.home, name='home'),
    path('logout/', views.logout_view, name='logout'),

    # Empleados
    path('empleados/', views.empleado_list, name='empleado_list'),
    path('empleados/nuevo/', views.empleado_create, name='empleado_create'),
    path('empleados/<int:pk>/', views.empleado_detail, name='empleado_detail'),
    path('empleados/<int:pk>/editar/', views.empleado_update, name='empleado_update'),
    path('empleados/<int:pk>/eliminar/', views.empleado_delete, name='empleado_delete'),
    path('empleados/<int:pk>/rol/', views.empleado_rol, name='empleado_rol'),
    path('empleados/<int:pk>/contrasena/', views.empleado_contrasena, name='empleado_contrasena'),

    # Departamentos
    path('departamentos/', views.departamento_list, name='departamento_list'),
    path('departamentos/nuevo/', views.departamento_create, name='departamento_create'),
    path('departamentos/<int:pk>/', views.departamento_detail, name='departamento_detail'),
    path('departamentos/<int:pk>/editar/', views.departamento_update, name='departamento_update'),
    path('departamentos/<int:pk>/eliminar/', views.departamento_delete, name='departamento_delete'),
    path('departamentos/<int:pk>/reactivar/', views.departamento_reactivar, name='departamento_reactivar'),

    # Proveedores
    path('proveedores/', views.proveedor_list, name='proveedor_list'),
    path('proveedores/nuevo/', views.proveedor_create, name='proveedor_create'),
    path('proveedores/<int:pk>/', views.proveedor_detail, name='proveedor_detail'),
    path('proveedores/<int:pk>/editar/', views.proveedor_update, name='proveedor_update'),
    path('proveedores/<int:pk>/eliminar/', views.proveedor_delete, name='proveedor_delete'),
    path('proveedores/<int:pk>/reactivar/', views.proveedor_reactivar, name='proveedor_reactivar'),

    # Roles y permisos (consulta)
    path('roles/', views.roles_list, name='roles_list'),

    # Perfil
    path('perfil/', views.perfil, name='perfil'),
    path('perfil/editar/', views.perfil_editar, name='perfil_editar'),
    path('perfil/contrasena/', views.perfil_contrasena, name='perfil_contrasena'),

    # Auditoría
    path('auditoria/', views.auditoria_list, name='auditoria_list'),
]
