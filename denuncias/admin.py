from django.contrib import admin

from .models import DecisaoModeracao, Denuncia


class DecisaoModeracaoInline(admin.TabularInline):
    model = DecisaoModeracao
    extra = 0
    fields = ('resultado', 'acao', 'dias_suspensao', 'justificativa', 'administrador', 'decidida_em')
    readonly_fields = ('administrador', 'decidida_em')

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Denuncia)
class DenunciaAdmin(admin.ModelAdmin):
    list_display = ('motivo', 'alvo', 'denunciante', 'status', 'criada_em')
    list_filter = ('status', 'motivo')
    search_fields = ('descricao', 'denunciante__username')
    readonly_fields = ('denunciante', 'usuario', 'carona', 'avaliacao', 'motivo', 'descricao',
                       'status', 'criada_em')
    inlines = [DecisaoModeracaoInline]

    def save_formset(self, request, form, formset, change):
        for decisao in formset.save(commit=False):
            decisao.administrador = request.user
            decisao.save()
        formset.save_m2m()


@admin.register(DecisaoModeracao)
class DecisaoModeracaoAdmin(admin.ModelAdmin):
    list_display = ('denuncia', 'resultado', 'acao', 'dias_suspensao', 'administrador',
                    'decidida_em')
    list_filter = ('resultado', 'acao')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
