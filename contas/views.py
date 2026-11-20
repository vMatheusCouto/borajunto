from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from avaliacoes.models import Avaliacao
from caronas.forms import BuscaForm
from caronas.models import Carona, Reserva

from .forms import EditarPerfilForm, EntrarForm
from .models import Perfil


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
               .select_related('motorista__perfil')
               .defer('motorista__perfil__foto'))
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
    como_motorista = Carona.objects.filter(motorista=request.user, status='concluida').count()
    como_passageiro = Reserva.objects.filter(
        passageiro=request.user, status='aceita', carona__status='concluida').count()
    return render(request, 'contas/perfil.html', {
        'caronas': como_motorista + como_passageiro,
        'reputacao': Avaliacao.objects.reputacao(request.user),
    })


@login_required
def editar_perfil(request):
    perfil = get_object_or_404(Perfil, usuario=request.user)
    form = EditarPerfilForm(request.POST or None, request.FILES or None, instance=perfil)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Perfil atualizado.')
        return redirect('contas:perfil')
    return render(request, 'contas/editar_perfil.html', {'form': form, 'perfil': perfil})


@login_required
def foto(request, usuario_id):
    perfil = get_object_or_404(Perfil, usuario_id=usuario_id, foto__isnull=False)
    resposta = HttpResponse(bytes(perfil.foto), content_type='image/jpeg')
    resposta['Cache-Control'] = 'private, max-age=31536000, immutable'
    return resposta
