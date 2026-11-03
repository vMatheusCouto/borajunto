from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from caronas.models import Carona, Reserva

from .models import Avaliacao

NOTAS = range(1, 6)


def participantes(carona):
    passageiros = [r.passageiro for r in carona.reservas.filter(
        status=Reserva.Status.ACEITA).select_related('passageiro__perfil')]
    return [carona.motorista, *passageiros]


@login_required
def avaliar(request, pk):
    carona = get_object_or_404(Carona.objects.select_related('motorista'), pk=pk,
                               status=Carona.Status.CONCLUIDA)
    pessoas = participantes(carona)
    if request.user not in pessoas:
        raise Http404
    avaliados = [p for p in pessoas if p != request.user]
    anteriores = dict(Avaliacao.objects.filter(carona=carona, avaliador=request.user)
                      .values_list('avaliado_id', 'nota'))

    if request.method == 'POST':
        salvas = 0
        for pessoa in avaliados:
            nota = request.POST.get(f'nota_{pessoa.pk}', '')
            if nota.isdigit() and int(nota) in NOTAS:
                Avaliacao.objects.update_or_create(
                    carona=carona, avaliador=request.user, avaliado=pessoa,
                    defaults={'nota': int(nota)})
                salvas += 1
        if salvas:
            messages.success(request, 'Avaliação registrada. Obrigado!')
            aba = '' if carona.motorista == request.user else '?aba=solicitei'
            return redirect(reverse('caronas:viagens') + aba)
        messages.error(request, 'Escolha de 1 a 5 estrelas para pelo menos uma pessoa.')

    for pessoa in avaliados:
        pessoa.nota_anterior = anteriores.get(pessoa.pk)
        pessoa.papel = 'Motorista' if pessoa == carona.motorista else 'Passageiro'
    return render(request, 'avaliacoes/avaliar.html', {
        'carona': carona, 'avaliados': avaliados, 'notas': NOTAS})
