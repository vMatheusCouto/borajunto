from django.contrib import admin

from .models import Carona, Reserva


@admin.register(Carona)
class CaronaAdmin(admin.ModelAdmin):
    list_display = ('origem', 'destino', 'data_hora', 'motorista', 'vagas', 'status')
    list_filter = ('status',)
    search_fields = ('origem', 'destino')


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ('carona', 'passageiro', 'status', 'criada_em')
    list_filter = ('status',)
    search_fields = ('passageiro__username', 'carona__origem', 'carona__destino')
