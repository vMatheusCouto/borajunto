from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from notificacoes.models import Notificacao

from .forms import TrajetoForm, VagasForm
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
        if form.is_valid():
            data_hora = datetime.strptime(trajeto['data'] + ' ' + trajeto['horario'], '%Y-%m-%d %H:%M')
            Carona.objects.create(
                motorista=request.user,
                origem=trajeto['origem'],
                destino=trajeto['destino'],
                ponto_encontro=trajeto['ponto_encontro'],
                data_hora=timezone.make_aware(data_hora),
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
    """Detalhes da carona com a opção de solicitar ou cancelar a vaga (RF14, UC05)."""
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
    """Registra a solicitação de vaga como pendente e avisa o motorista (UC05)."""
    detalhe_url = reverse('caronas:detalhe', args=[pk])
    if request.method != 'POST':
        return redirect(detalhe_url)

    with transaction.atomic():
        # Trava a carona para que duas solicitações não disputem a última vaga (UC05 E1).
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
def viagens(request):
    if request.GET.get('aba') == 'solicitei':
        reservas = Reserva.objects.filter(passageiro=request.user).order_by('-criada_em')
        return render(request, 'caronas/viagens.html', {'aba': 'solicitei', 'reservas': reservas})

    caronas = list(Carona.objects.filter(
        motorista=request.user,
        status__in=['publicada', 'lotada', 'em_andamento'],
    ))
    for carona in caronas:
        carona.confirmadas = carona.reservas.filter(status='aceita')
        carona.pendentes = carona.reservas.filter(status='pendente')
        carona.livres = range(carona.vagas - carona.confirmadas.count())
    return render(request, 'caronas/viagens.html', {'aba': 'ofereci', 'caronas': caronas})


@login_required
def aceitar(request, pk):
    reserva = get_object_or_404(Reserva, pk=pk, carona__motorista=request.user)
    carona = reserva.carona
    if request.method != 'POST':
        return redirect('caronas:viagens')

    with transaction.atomic():
        confirmadas = carona.reservas.filter(status='aceita').count()
        if reserva.status != 'pendente':
            messages.error(request, 'Essa solicitação já foi respondida.')
        elif confirmadas >= carona.vagas:
            messages.error(request, 'Todas as vagas dessa carona já estão ocupadas.')
        else:
            reserva.status = 'aceita'
            reserva.save()
            if confirmadas + 1 == carona.vagas:
                carona.status = 'lotada'
                carona.save()
            Notificacao.objects.create(
                destinatario=reserva.passageiro,
                carona=carona,
                tipo='decisao',
                mensagem=f'Sua vaga em {carona.origem} → {carona.destino} foi confirmada.',
            )
            messages.success(request, 'Vaga confirmada.')
    return redirect('caronas:viagens')


@login_required
def recusar(request, pk):
    reserva = get_object_or_404(Reserva, pk=pk, carona__motorista=request.user)
    carona = reserva.carona
    if request.method != 'POST':
        return redirect('caronas:viagens')

    if reserva.status != 'pendente':
        messages.error(request, 'Essa solicitação já foi respondida.')
    else:
        reserva.status = 'recusada'
        reserva.save()
        Notificacao.objects.create(
            destinatario=reserva.passageiro,
            carona=carona,
            tipo='decisao',
            mensagem=f'Sua vaga em {carona.origem} → {carona.destino} foi recusada.',
        )
        messages.success(request, 'Solicitação recusada.')
    return redirect('caronas:viagens')
