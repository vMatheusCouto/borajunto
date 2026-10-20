from django.contrib import admin

from .models import Carona


@admin.register(Carona)
class CaronaAdmin(admin.ModelAdmin):
    list_display = ('origem', 'destino', 'data_hora', 'motorista', 'vagas', 'status')
    list_filter = ('status',)
    search_fields = ('origem', 'destino')
