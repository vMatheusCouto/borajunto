from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'contas'

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('perfil/', views.perfil, name='perfil'),
    path('perfil/editar/', views.editar_perfil, name='editar_perfil'),
    path('perfil/foto/<int:usuario_id>/', views.foto, name='foto'),
    path('entrar/', views.EntrarView.as_view(), name='entrar'),
    path('sair/', auth_views.LogoutView.as_view(), name='sair'),
]
