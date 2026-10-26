from django.contrib import admin

from .models import Avaliacao


@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ('avaliado', 'avaliador', 'nota', 'carona', 'removida', 'criada_em')
    list_filter = ('nota', 'removida')
    search_fields = ('avaliado__username', 'avaliador__username')
