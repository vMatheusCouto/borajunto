from datetime import timedelta

from django.utils import timezone

from caronas.models import Carona, Reserva
from notificacoes.models import Notificacao

from .models import DecisaoModeracao

MOTIVO_MODERACAO = 'Cancelada pela moderação.'


def aplicar_decisao(decisao):
    denuncia = decisao.denuncia
    denuncia.status = decisao.resultado
    denuncia.save(update_fields=['status'])

    Acao = DecisaoModeracao.Acao
    if decisao.acao == Acao.SUSPENDER_CONTA:
        _suspender_conta(denuncia.responsavel, decisao.dias_suspensao)
    elif decisao.acao == Acao.CANCELAR_CARONA:
        carona = denuncia.carona
        carona.cancelar(
            MOTIVO_MODERACAO,
            f'A carona {carona.origem} → {carona.destino} foi cancelada pela moderação.')
    elif decisao.acao == Acao.REMOVER_AVALIACAO:
        denuncia.avaliacao.removida = True
        denuncia.avaliacao.save(update_fields=['removida'])

    _notificar_envolvidos(decisao)


def _suspender_conta(usuario, dias):
    agora = timezone.now()
    if dias:
        fim = agora + timedelta(days=dias)
        usuario.perfil.suspensa_ate = fim
        usuario.perfil.save(update_fields=['suspensa_ate'])
    else:
        fim = None
        usuario.is_active = False
        usuario.save(update_fields=['is_active'])

    caronas = Carona.objects.select_for_update().filter(
        motorista=usuario, status__in=(Carona.Status.PUBLICADA, Carona.Status.LOTADA))
    if fim:
        caronas = caronas.filter(data_hora__lt=fim)
    for carona in caronas:
        carona.cancelar(
            MOTIVO_MODERACAO,
            f'A carona {carona.origem} → {carona.destino} foi cancelada pela moderação.')

    reservas = Reserva.objects.select_related('carona').filter(
        passageiro=usuario, status__in=Reserva.ATIVAS,
        carona__status__in=(Carona.Status.PUBLICADA, Carona.Status.LOTADA))
    if fim:
        reservas = reservas.filter(carona__data_hora__lt=fim)
    nome = usuario.get_full_name() or usuario.username
    for reserva in reservas:
        reserva.status = Reserva.Status.CANCELADA
        reserva.save(update_fields=['status', 'atualizada_em'])
        carona = reserva.carona
        carona.atualizar_lotacao()
        Notificacao.objects.create(
            destinatario=carona.motorista,
            carona=carona,
            tipo=Notificacao.Tipo.CANCELAMENTO,
            mensagem=f'A reserva de {nome} em {carona.origem} → {carona.destino} foi cancelada pela moderação.'[:255],
        )


def _notificar_envolvidos(decisao):
    denuncia = decisao.denuncia
    motivo = denuncia.get_motivo_display()
    avisos = [Notificacao(
        destinatario=denuncia.denunciante,
        tipo=Notificacao.Tipo.MODERACAO,
        mensagem=f'Sua denúncia por "{motivo}" foi analisada e considerada '
                 f'{decisao.get_resultado_display().lower()}.',
    )]

    Acao = DecisaoModeracao.Acao
    carona = None
    if decisao.acao == Acao.SUSPENDER_CONTA:
        if decisao.dias_suspensao:
            fim = timezone.localtime(denuncia.responsavel.perfil.suspensa_ate)
            efeito = f'Sua conta foi suspensa até {fim:%d/%m/%Y às %H:%M}'
        else:
            efeito = 'Sua conta foi suspensa'
    elif decisao.acao == Acao.CANCELAR_CARONA:
        carona = denuncia.carona
        efeito = f'Sua carona {carona.origem} → {carona.destino} foi cancelada pela moderação'
    elif decisao.acao == Acao.REMOVER_AVALIACAO:
        efeito = 'Uma avaliação sua foi removida pela moderação'
    else:
        efeito = None

    if efeito:
        avisos.append(Notificacao(
            destinatario=denuncia.responsavel,
            carona=carona,
            tipo=Notificacao.Tipo.MODERACAO,
            mensagem=f'{efeito} após uma denúncia por "{motivo}".'[:255],
        ))
    Notificacao.objects.bulk_create(avisos)
