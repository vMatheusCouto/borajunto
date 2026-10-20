from django.contrib import admin

from .models import Perfil


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('matricula', 'usuario', 'curso', 'campus', 'atualizado_em')
    search_fields = ('matricula', 'usuario__first_name', 'usuario__last_name', 'usuario__email')
    # Dados vindos do SUAP não são editados no BoraJunto (RN02).
    readonly_fields = ('usuario', 'matricula', 'curso', 'campus', 'foto_url', 'atualizado_em')
