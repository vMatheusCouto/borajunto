from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from notificacoes.models import Notificacao

from .forms import TrajetoForm, VagasForm
from .models import Carona, Reserva

CHAVE_RASCUNHO = 'carona_rascunho'
ATIVAS = (Carona.Status.PUBLICADA, Carona.Status.LOTADA, Carona.Status.EM_ANDAMENTO)


@login_required
def oferecer(request):
    form = TrajetoForm(request.POST or None, initial=request.session.get(CHAVE_RASCUNHO))
    if form.is_valid():
        request.session[CHAVE_RASCUNHO] = form.para_sessao()
        return redirect('caronas:oferecer_vagas')
    return render(request, 'caronas/oferecer_trajeto.html', {'form': form})


@login_required
def oferecer_vagas(request):
    rascunho = request.session.get(CHAVE_RASCUNHO)
    if not rascunho:
        return redirect('caronas:oferecer')
    form = VagasForm(request.POST or None)
    if form.is_valid():
        trajeto = TrajetoForm(rascunho)
        if not trajeto.is_valid():
            messages.error(request, 'O horário escolhido já passou. Confira o trajeto de novo.')
            return redirect('caronas:oferecer')
        dados = trajeto.cleaned_data
        Carona.objects.create(
            motorista=request.user,
            origem=dados['origem'],
            destino=dados['destino'],
            ponto_encontro=dados['ponto_encontro'],
            data_hora=dados['data_hora'],
            vagas=form.cleaned_data['vagas'],
            observacoes=form.cleaned_data['observacoes'],
        )
        del request.session[CHAVE_RASCUNHO]
        messages.success(request, 'Carona publicada. Você recebe uma notificação a cada solicitação.')
        return redirect('caronas:viagens')
    return render(request, 'caronas/oferecer_vagas.html', {'form': form, 'rascunho': rascunho})


@login_required
def viagens(request):
    aba = 'solicitei' if request.GET.get('aba') == 'solicitei' else 'ofereci'
    contexto = {'aba': aba}
    if aba == 'ofereci':
        reservas = Reserva.objects.select_related('passageiro__perfil').order_by('criada_em')
        caronas = (request.user.caronas.filter(status__in=ATIVAS)
                   .com_vagas_restantes()
                   .prefetch_related(
                       Prefetch('reservas', queryset=reservas.filter(status=Reserva.Status.PENDENTE),
                                to_attr='pendentes'),
                       Prefetch('reservas', queryset=reservas.filter(status=Reserva.Status.ACEITA),
                                to_attr='confirmadas')))
        for carona in caronas:
            carona.assentos = carona.confirmadas + [None] * carona.vagas_restantes
        contexto['caronas'] = caronas
    else:
        contexto['reservas'] = (request.user.reservas
                                .select_related('carona__motorista')
                                .order_by('-carona__data_hora'))
    return render(request, 'caronas/viagens.html', contexto)


@login_required
@require_POST
def decidir(request, pk, decisao):
    reserva = get_object_or_404(Reserva.objects.select_related('carona', 'passageiro'),
                                pk=pk, carona__motorista=request.user)
    nome = reserva.passageiro.get_full_name() or reserva.passageiro.username
    try:
        if decisao == 'aceitar':
            reserva.aceitar()
        else:
            reserva.recusar()
    except ValidationError as erro:
        messages.error(request, erro.messages[0])
        return redirect('caronas:viagens')

    aceita = decisao == 'aceitar'
    Notificacao.objects.create(
        destinatario=reserva.passageiro,
        carona=reserva.carona,
        tipo=Notificacao.Tipo.DECISAO,
        mensagem=(f'Sua vaga em {reserva.carona.origem} → {reserva.carona.destino} foi '
                  f'{"confirmada" if aceita else "recusada"}.'),
    )
    messages.success(request, f'Vaga de {nome} confirmada.' if aceita else f'Solicitação de {nome} recusada.')
    return redirect('caronas:viagens')
