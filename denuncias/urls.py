from django.urls import path

from . import views

app_name = 'denuncias'

urlpatterns = [
    path('', views.escolher, name='escolher'),
    path('usuario/<int:pk>/', views.registrar, {'tipo': 'usuario'}, name='usuario'),
    path('carona/<int:pk>/', views.registrar, {'tipo': 'carona'}, name='carona'),
    path('avaliacao/<int:pk>/', views.registrar, {'tipo': 'avaliacao'}, name='avaliacao'),
]
