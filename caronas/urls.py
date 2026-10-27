from django.urls import path

from . import views

app_name = 'caronas'

urlpatterns = [
    path('oferecer/', views.oferecer, name='oferecer'),
    path('oferecer/vagas/', views.oferecer_vagas, name='oferecer_vagas'),
    path('<int:pk>/', views.detalhe, name='detalhe'),
    path('<int:pk>/solicitar/', views.solicitar, name='solicitar'),
    path('viagens/', views.viagens, name='viagens'),
    path('reservas/<int:pk>/aceitar/', views.aceitar, name='aceitar'),
    path('reservas/<int:pk>/recusar/', views.recusar, name='recusar'),
]
