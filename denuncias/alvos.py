"""Identifica o alvo de uma denúncia a partir da URL (UC09, passo 2)."""

from django.contrib.auth import get_user_model
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateformat import format as formatar_data

from avaliacoes.models import Avaliacao
from caronas.models import Carona


def nome(usuario):
    return usuario.get_full_name() or usuario.username


def trajeto(carona):
    data = formatar_data(timezone.localtime(carona.data_hora), 'j b')  # "30 ago", como no protótipo
    return f'{carona.origem} → {carona.destino}, {data}'


def resolver(request, tipo, pk):
    """Devolve o campo do alvo, o objeto e o texto do card "Sobre".

    Ninguém denuncia a si mesmo nem a própria carona, e avaliações só podem ser
    denunciadas por quem as recebeu (RNF06).
    """
    if tipo == 'usuario':
        usuario = get_object_or_404(get_user_model().objects.select_related('perfil'),
                                    pk=pk, is_active=True)
        if usuario == request.user:
            raise Http404
        perfil = getattr(usuario, 'perfil', None)
        curso = f' · {perfil.curso}' if perfil and perfil.curso else ''
        return 'usuario', usuario, f'{nome(usuario)}{curso}'

    if tipo == 'carona':
        carona = get_object_or_404(Carona.objects.select_related('motorista'), pk=pk)
        if carona.motorista == request.user:
            raise Http404
        return 'carona', carona, f'{nome(carona.motorista)} · {trajeto(carona)}'

    if tipo == 'avaliacao':
        avaliacao = get_object_or_404(
            Avaliacao.objects.select_related('avaliador', 'carona'),
            pk=pk, avaliado=request.user, removida=False)
        estrelas = 'estrela' if avaliacao.nota == 1 else 'estrelas'
        return ('avaliacao', avaliacao,
                f'{avaliacao.nota} {estrelas} de {nome(avaliacao.avaliador)} · '
                f'{trajeto(avaliacao.carona)}')

    raise Http404
