from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from avaliacoes.models import Avaliacao
from caronas.forms import BuscaForm
from caronas.models import Carona, caronas_concluidas

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
        'filtrada': any(request.GET.values()),
        'caronas': caronas,
        'notificacoes_nao_lidas': request.user.notificacoes.filter(lida=False).exists(),
    })


@login_required
def perfil(request):
    return render(request, 'contas/perfil.html', {
        'caronas': caronas_concluidas(request.user),
        'reputacao': Avaliacao.objects.reputacao(request.user),
    })


@login_required
def perfil_publico(request, pk):
    """Perfil de outro estudante: dados do SUAP, reputação e próximas caronas (RF25)."""
    if pk == request.user.pk:
        return redirect('contas:perfil')

    pessoa = get_object_or_404(get_user_model(), pk=pk, is_active=True)
    return render(request, 'contas/perfil_publico.html', {
        'pessoa': pessoa,
        'caronas': caronas_concluidas(pessoa),
        'reputacao': Avaliacao.objects.reputacao(pessoa),
        'proximas': Carona.objects.disponiveis().filter(motorista=pessoa),
    })
