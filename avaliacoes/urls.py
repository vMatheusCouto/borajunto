from django.urls import path

from . import views

app_name = 'avaliacoes'

urlpatterns = [
    path('carona/<int:pk>/', views.avaliar, name='avaliar'),
]
