from datetime import timedelta

from django.utils import timezone

from .models import Notificacao

ANTECEDENCIA = timedelta(minutes=60)


def lembrar(carona):
    """Lembrete para o motorista e os passageiros confirmados, uma vez por pessoa (RF22)."""
    from caronas.models import Reserva

    pessoas = [carona.motorista_id, *carona.reservas.filter(
        status=Reserva.Status.ACEITA).values_list('passageiro_id', flat=True)]
    horario = timezone.localtime(carona.data_hora)
    criados = 0
    for pessoa in pessoas:
        _, novo = Notificacao.objects.get_or_create(
            destinatario_id=pessoa, carona=carona, tipo=Notificacao.Tipo.LEMBRETE,
            defaults={'mensagem': f'Sua carona {carona.origem} → {carona.destino} sai às {horario:%H:%M}.'})
        criados += novo
    return criados


def perto_do_horario(carona, agora=None):
    agora = agora or timezone.now()
    return agora < carona.data_hora <= agora + ANTECEDENCIA


def enviar_lembretes(agora=None):
    """Gera os lembretes das caronas que saem nos próximos 60 minutos."""
    from caronas.models import Carona

    agora = agora or timezone.now()
    caronas = Carona.objects.filter(
        status__in=[Carona.Status.PUBLICADA, Carona.Status.LOTADA],
        data_hora__gt=agora, data_hora__lte=agora + ANTECEDENCIA)
    return sum(lembrar(carona) for carona in caronas)
