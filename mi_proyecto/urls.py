"""URL configuration for mi_proyecto project."""
from django.contrib import admin
from django.urls import path, include

from login import views as login_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('login.urls')),
]

# Páginas de error personalizadas
handler403 = 'login.views.handler403'
handler404 = 'login.views.handler404'
handler500 = 'login.views.handler500'
