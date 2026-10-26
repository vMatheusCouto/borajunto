from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from caronas.forms import BuscaForm
from caronas.models import Carona

from .forms import EntrarForm


class EntrarView(auth_views.LoginView):
    form_class = EntrarForm
    template_name = 'contas/entrar.html'
    redirect_authenticated_user = True


def saudacao(agora):
    if agora.hour < 12:
        return 'Bom dia'
    if agora.hour < 18:
        return 'Boa tarde'
    return 'Boa noite'


@login_required
def inicio(request):
    """Tela inicial: dados do perfil, busca e lista das caronas disponíveis (UC04)."""
    busca = BuscaForm(request.GET or None)
    caronas = (Carona.objects.disponiveis()
               .exclude(motorista=request.user)  # RN09
               .com_reputacao_do_motorista()
               .select_related('motorista'))
    if busca.is_bound and busca.is_valid():
        caronas = busca.filtrar(caronas)
    return render(request, 'contas/inicio.html', {
        'saudacao': saudacao(timezone.localtime()),
        'busca': busca,
        'caronas': caronas,
        'notificacoes_nao_lidas': request.user.notificacoes.filter(lida=False).exists(),
    })
