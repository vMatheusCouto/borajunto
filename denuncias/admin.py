from django.contrib import admin

from .models import DecisaoModeracao, Denuncia


class DecisaoModeracaoInline(admin.TabularInline):
    model = DecisaoModeracao
    extra = 0
    readonly_fields = ('decidida_em',)


@admin.register(Denuncia)
class DenunciaAdmin(admin.ModelAdmin):
    list_display = ('motivo', 'alvo', 'denunciante', 'status', 'criada_em')
    list_filter = ('status', 'motivo')
    search_fields = ('descricao', 'denunciante__username')
    readonly_fields = ('denunciante', 'usuario', 'carona', 'avaliacao', 'motivo', 'descricao',
                       'criada_em')
    inlines = [DecisaoModeracaoInline]


@admin.register(DecisaoModeracao)
class DecisaoModeracaoAdmin(admin.ModelAdmin):
    list_display = ('denuncia', 'resultado', 'acao', 'administrador', 'decidida_em')
    list_filter = ('resultado', 'acao')
    readonly_fields = ('decidida_em',)
