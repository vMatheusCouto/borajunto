from django.contrib import admin

from .models import Notificacao


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ('destinatario', 'tipo', 'carona', 'lida', 'criada_em')
    list_filter = ('tipo', 'lida')
    search_fields = ('destinatario__username', 'mensagem')
