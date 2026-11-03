from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from notificacoes.lembretes import lembrar, perto_do_horario
from notificacoes.models import Notificacao

from .forms import CancelarCaronaForm, EditarCaronaForm, TrajetoForm, VagasForm
from .models import Carona, Reserva


@login_required
def oferecer(request):
    if request.method == 'POST':
        form = TrajetoForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            request.session['nova_carona'] = {
                'origem': dados['origem'],
                'destino': dados['destino'],
                'ponto_encontro': dados['ponto_encontro'],
                'data': dados['data'].strftime('%Y-%m-%d'),
                'horario': dados['horario'].strftime('%H:%M'),
            }
            return redirect('caronas:oferecer_vagas')
    else:
        form = TrajetoForm(initial=request.session.get('nova_carona'))
    return render(request, 'caronas/oferecer_trajeto.html', {'form': form})


@login_required
def oferecer_vagas(request):
    trajeto = request.session.get('nova_carona')
    if trajeto is None:
        return redirect('caronas:oferecer')

    if request.method == 'POST':
        form = VagasForm(request.POST)
        data_hora = timezone.make_aware(
            datetime.strptime(trajeto['data'] + ' ' + trajeto['horario'], '%Y-%m-%d %H:%M'))
        if data_hora <= timezone.now():
            messages.error(request, 'O horário da carona já passou. Escolha um novo horário.')
            return redirect('caronas:oferecer')
        if form.is_valid():
            Carona.objects.create(
                motorista=request.user,
                origem=trajeto['origem'],
                destino=trajeto['destino'],
                ponto_encontro=trajeto['ponto_encontro'],
                data_hora=data_hora,
                vagas=form.cleaned_data['vagas'],
                observacoes=form.cleaned_data['observacoes'],
            )
            del request.session['nova_carona']
            messages.success(request, 'Carona publicada. Você recebe uma notificação a cada solicitação.')
            return redirect('caronas:viagens')
    else:
        form = VagasForm()
    return render(request, 'caronas/oferecer_vagas.html', {'form': form})


@login_required
def detalhe(request, pk):
    carona = get_object_or_404(
        Carona.objects.com_vagas_restantes().com_reputacao_do_motorista()
        .select_related('motorista__perfil'),
        pk=pk,
    )
    motorista = carona.motorista
    caronas_do_motorista = (
        Carona.objects.filter(motorista=motorista, status='concluida').count()
        + Reserva.objects.filter(passageiro=motorista, status='aceita', carona__status='concluida').count()
    )
    return render(request, 'caronas/detalhe.html', {
        'carona': carona,
        'caronas_do_motorista': caronas_do_motorista,
        'livres': range(max(carona.vagas_restantes, 0)),
        'ocupadas': range(carona.vagas - max(carona.vagas_restantes, 0)),
        'reserva': carona.reservas.filter(passageiro=request.user, status__in=Reserva.ATIVAS).first(),
        'disponivel': Carona.objects.disponiveis().filter(pk=carona.pk).exists(),
    })


@login_required
def solicitar(request, pk):
    detalhe_url = reverse('caronas:detalhe', args=[pk])
    if request.method != 'POST':
        return redirect(detalhe_url)

    with transaction.atomic():
        carona = get_object_or_404(Carona.objects.select_for_update(), pk=pk)
        saida = carona.data_hora
        proximas = Reserva.objects.filter(
            passageiro=request.user,
            status__in=Reserva.ATIVAS,
            carona__data_hora__gt=saida - timedelta(minutes=60),
            carona__data_hora__lt=saida + timedelta(minutes=60),
        ).exclude(carona=carona)

        if carona.motorista_id == request.user.pk:
            messages.error(request, 'Você não pode solicitar vaga na sua própria carona.')
        elif not Carona.objects.disponiveis().filter(pk=carona.pk).exists():
            messages.error(request, 'Essa carona não está mais recebendo solicitações.')
        elif carona.reservas.filter(passageiro=request.user, status__in=Reserva.ATIVAS).exists():
            messages.error(request, 'Você já solicitou uma vaga nessa carona.')
        elif proximas.exists():
            messages.error(request, 'Você já tem uma reserva em outra carona com saída a menos de 60 minutos dessa.')
        else:
            Reserva.objects.create(carona=carona, passageiro=request.user)
            nome = request.user.get_full_name() or request.user.username
            Notificacao.objects.create(
                destinatario=carona.motorista,
                carona=carona,
                tipo='solicitacao',
                mensagem=f'{nome} pediu uma vaga em {carona.origem} → {carona.destino}.',
            )
            messages.success(request, 'Vaga solicitada. Avisamos quando o motorista responder.')
            return redirect(reverse('caronas:viagens') + '?aba=solicitei')
    return redirect(detalhe_url)


@login_required
def cancelar(request, pk):
    reserva = get_object_or_404(Reserva, pk=pk, passageiro=request.user)
    if request.method != 'POST':
        return redirect(reverse('caronas:viagens') + '?aba=solicitei')

    with transaction.atomic():
        carona = Carona.objects.select_for_update().get(pk=reserva.carona_id)
        reserva = Reserva.objects.select_related('carona').get(pk=reserva.pk)
        if not reserva.cancelavel:
            messages.error(request, 'Essa solicitação não pode mais ser cancelada.')
        else:
            confirmada = reserva.status == Reserva.Status.ACEITA
            reserva.status = Reserva.Status.CANCELADA
            reserva.save()
            carona.atualizar_lotacao()
            nome = request.user.get_full_name() or request.user.username
            Notificacao.objects.create(
                destinatario=carona.motorista,
                carona=carona,
                tipo='cancelamento',
                mensagem=f'{nome} cancelou {"a reserva" if confirmada else "o pedido de vaga"} em {carona.origem} → {carona.destino}.',
            )
            messages.success(request, 'Reserva cancelada.' if confirmada else 'Solicitação cancelada.')
    return redirect(reverse('caronas:viagens') + '?aba=solicitei')


@login_required
def viagens(request):
    if request.GET.get('aba') == 'solicitei':
        reservas = (Reserva.objects.filter(passageiro=request.user)
                    .select_related('carona__motorista').order_by('-criada_em'))
        return render(request, 'caronas/viagens.html', {'aba': 'solicitei', 'reservas': reservas})

    caronas = Carona.objects.filter(
        motorista=request.user,
        status__in=['publicada', 'lotada', 'em_andamento'],
    ).prefetch_related(
        Prefetch('reservas', to_attr='confirmadas', queryset=Reserva.objects.filter(
            status=Reserva.Status.ACEITA).select_related('passageiro')),
        Prefetch('reservas', to_attr='pendentes', queryset=Reserva.objects.filter(
            status=Reserva.Status.PENDENTE).select_related('passageiro__perfil')),
    )
    for carona in caronas:
        carona.livres = range(max(carona.vagas - len(carona.confirmadas), 0))
    historico = (Carona.objects.filter(motorista=request.user, status__in=['concluida', 'cancelada'])
                 .order_by('-data_hora'))
    return render(request, 'caronas/viagens.html', {
        'aba': 'ofereci', 'caronas': caronas, 'historico': historico})


@login_required
def aceitar(request, pk):
    reserva = get_object_or_404(Reserva, pk=pk, carona__motorista=request.user)
    if request.method != 'POST':
        return redirect('caronas:viagens')

    with transaction.atomic():
        carona = Carona.objects.select_for_update().get(pk=reserva.carona_id)
        reserva.refresh_from_db()
        confirmadas = carona.reservas.filter(status=Reserva.Status.ACEITA).count()
        if reserva.status != Reserva.Status.PENDENTE:
            messages.error(request, 'Essa solicitação já foi respondida.')
        elif not carona.aberta or carona.data_hora <= timezone.now():
            messages.error(request, 'Essa carona não recebe mais passageiros.')
        elif confirmadas >= carona.vagas:
            messages.error(request, 'Todas as vagas dessa carona já estão ocupadas.')
        else:
            reserva.status = Reserva.Status.ACEITA
            reserva.save()
            carona.atualizar_lotacao()
            Notificacao.objects.create(
                destinatario=reserva.passageiro,
                carona=carona,
                tipo='decisao',
                mensagem=f'Sua vaga em {carona.origem} → {carona.destino} foi confirmada.',
            )
            if perto_do_horario(carona):
                lembrar(carona)
            messages.success(request, 'Vaga confirmada.')
    return redirect('caronas:viagens')


@login_required
def recusar(request, pk):
    reserva = get_object_or_404(Reserva, pk=pk, carona__motorista=request.user)
    if request.method != 'POST':
        return redirect('caronas:viagens')

    with transaction.atomic():
        reserva = Reserva.objects.select_for_update().select_related('carona').get(pk=reserva.pk)
        carona = reserva.carona
        if reserva.status != Reserva.Status.PENDENTE:
            messages.error(request, 'Essa solicitação já foi respondida.')
        else:
            reserva.status = Reserva.Status.RECUSADA
            reserva.save()
            Notificacao.objects.create(
                destinatario=reserva.passageiro,
                carona=carona,
                tipo='decisao',
                mensagem=f'Sua vaga em {carona.origem} → {carona.destino} foi recusada.',
            )
            messages.success(request, 'Solicitação recusada.')
    return redirect('caronas:viagens')


def notificar_passageiros(carona, tipo, mensagem, status=(Reserva.Status.ACEITA,)):
    passageiros = carona.reservas.filter(status__in=status).values_list('passageiro', flat=True)
    Notificacao.objects.bulk_create(
        Notificacao(destinatario_id=passageiro, carona=carona, tipo=tipo, mensagem=mensagem)
        for passageiro in passageiros
    )


def carona_do_motorista(request, pk):
    return get_object_or_404(Carona.objects.select_for_update(), pk=pk, motorista=request.user)


@login_required
def editar(request, pk):
    carona = get_object_or_404(Carona, pk=pk, motorista=request.user)
    if not carona.aberta:
        messages.error(request, 'Essa carona não pode mais ser editada.')
        return redirect('caronas:viagens')

    confirmadas = carona.reservas.filter(status=Reserva.Status.ACEITA).count()
    local = timezone.localtime(carona.data_hora)
    inicial = {
        'origem': carona.origem, 'destino': carona.destino, 'ponto_encontro': carona.ponto_encontro,
        'data': local.date(), 'horario': local.time().replace(second=0, microsecond=0),
        'vagas': carona.vagas, 'observacoes': carona.observacoes,
    }
    form = EditarCaronaForm(request.POST or None, initial=inicial, confirmadas=confirmadas)
    if request.method == 'POST' and form.is_valid():
        dados = form.cleaned_data
        with transaction.atomic():
            carona = carona_do_motorista(request, pk)
            if not carona.aberta:
                messages.error(request, 'Essa carona não pode mais ser editada.')
                return redirect('caronas:viagens')
            novo = {
                'origem': dados['origem'], 'destino': dados['destino'],
                'ponto_encontro': dados['ponto_encontro'],
                'data_hora': timezone.make_aware(datetime.combine(dados['data'], dados['horario'])),
            }
            atual = {
                'origem': carona.origem, 'destino': carona.destino,
                'ponto_encontro': carona.ponto_encontro,
                'data_hora': carona.data_hora.replace(second=0, microsecond=0),
            }
            relevante = atual != novo
            for campo, valor in novo.items():
                setattr(carona, campo, valor)
            carona.vagas = dados['vagas']
            carona.observacoes = dados['observacoes']
            carona.save()
            carona.atualizar_lotacao()
            if relevante:
                notificar_passageiros(
                    carona, Notificacao.Tipo.ALTERACAO,
                    f'A carona {carona.origem} → {carona.destino} mudou. Confira o novo horário e o ponto de encontro.')
        messages.success(request, 'Carona atualizada.' + (' Os passageiros confirmados foram avisados.' if relevante else ''))
        return redirect('caronas:viagens')
    return render(request, 'caronas/editar.html', {'form': form, 'carona': carona})


@login_required
def cancelar_carona(request, pk):
    carona = get_object_or_404(Carona, pk=pk, motorista=request.user)
    if not carona.aberta:
        messages.error(request, 'Essa carona não pode mais ser cancelada.')
        return redirect('caronas:viagens')

    form = CancelarCaronaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            carona = carona_do_motorista(request, pk)
            if carona.aberta:
                motivo = form.cleaned_data['motivo']
                notificar_passageiros(
                    carona, Notificacao.Tipo.CANCELAMENTO,
                    f'A carona {carona.origem} → {carona.destino} foi cancelada pelo motorista. Motivo: {motivo}'[:255],
                    status=Reserva.ATIVAS)
                carona.reservas.filter(status__in=Reserva.ATIVAS).update(status=Reserva.Status.CANCELADA)
                carona.status = Carona.Status.CANCELADA
                carona.motivo_cancelamento = motivo
                carona.save()
                messages.success(request, 'Carona cancelada. Os passageiros foram avisados.')
        return redirect('caronas:viagens')
    return render(request, 'caronas/cancelar.html', {'form': form, 'carona': carona})


@login_required
def iniciar(request, pk):
    if request.method != 'POST':
        return redirect('caronas:viagens')
    with transaction.atomic():
        carona = carona_do_motorista(request, pk)
        if not carona.pode_iniciar:
            messages.error(request, 'A carona só pode ser iniciada perto do horário de saída.')
        else:
            notificar_passageiros(
                carona, Notificacao.Tipo.DECISAO,
                f'A carona {carona.origem} → {carona.destino} já saiu e seu pedido não foi aceito.',
                status=(Reserva.Status.PENDENTE,))
            carona.reservas.filter(status=Reserva.Status.PENDENTE).update(status=Reserva.Status.RECUSADA)
            carona.status = Carona.Status.EM_ANDAMENTO
            carona.save()
            messages.success(request, 'Carona iniciada. Boa viagem!')
    return redirect('caronas:viagens')


@login_required
def concluir(request, pk):
    if request.method != 'POST':
        return redirect('caronas:viagens')
    with transaction.atomic():
        carona = carona_do_motorista(request, pk)
        if carona.status != Carona.Status.EM_ANDAMENTO:
            messages.error(request, 'Só uma carona em andamento pode ser concluída.')
        else:
            carona.status = Carona.Status.CONCLUIDA
            carona.save()
            notificar_passageiros(
                carona, Notificacao.Tipo.ALTERACAO,
                f'A carona {carona.origem} → {carona.destino} foi concluída. Avalie os participantes.')
            messages.success(request, 'Carona concluída.')
    return redirect('caronas:viagens')
