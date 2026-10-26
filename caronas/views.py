from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
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
