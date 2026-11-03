from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Avg, Count, F, OuterRef, Q, Subquery
from django.utils import timezone


class CaronaQuerySet(models.QuerySet):
    def disponiveis(self):
        return (self.com_vagas_restantes()
                .filter(status=Carona.Status.PUBLICADA, data_hora__gt=timezone.now(),
                        vagas_restantes__gt=0))

    def com_vagas_restantes(self):
        confirmadas = Count('reservas', filter=Q(reservas__status=Reserva.Status.ACEITA))
        return self.annotate(vagas_restantes=F('vagas') - confirmadas)

    def com_reputacao_do_motorista(self):
        from avaliacoes.models import Avaliacao

        recebidas = (Avaliacao.objects.validas()
                     .filter(avaliado=OuterRef('motorista'))
                     .values('avaliado'))
        return self.annotate(
            reputacao_media=Subquery(recebidas.annotate(m=Avg('nota')).values('m')),
            reputacao_quantidade=Subquery(recebidas.annotate(q=Count('id')).values('q')),
        )


class Carona(models.Model):
    ANTECEDENCIA_INICIO = timedelta(minutes=30)

    class Status(models.TextChoices):
        PUBLICADA = 'publicada', 'Publicada'
        LOTADA = 'lotada', 'Lotada'
        EM_ANDAMENTO = 'em_andamento', 'Em andamento'
        CONCLUIDA = 'concluida', 'Concluída'
        CANCELADA = 'cancelada', 'Cancelada'

    motorista = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='caronas',
    )
    origem = models.CharField(max_length=255)
    destino = models.CharField(max_length=255)
    ponto_encontro = models.CharField(max_length=255)
    data_hora = models.DateTimeField()
    vagas = models.PositiveSmallIntegerField()
    observacoes = models.TextField(blank=True)
    motivo_cancelamento = models.TextField(blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PUBLICADA,
    )
    criada_em = models.DateTimeField(auto_now_add=True)

    objects = CaronaQuerySet.as_manager()

    class Meta:
        ordering = ['data_hora']

    def __str__(self):
        return f'{self.origem} → {self.destino} ({self.data_hora:%d/%m/%Y %H:%M})'

    @property
    def aberta(self):
        return self.status in (self.Status.PUBLICADA, self.Status.LOTADA)

    @property
    def pode_iniciar(self):
        return self.aberta and timezone.now() >= self.data_hora - self.ANTECEDENCIA_INICIO

    def atualizar_lotacao(self):
        if not self.aberta:
            return
        confirmadas = self.reservas.filter(status=Reserva.Status.ACEITA).count()
        situacao = self.Status.LOTADA if confirmadas >= self.vagas else self.Status.PUBLICADA
        if situacao != self.status:
            self.status = situacao
            self.save(update_fields=['status'])


class Reserva(models.Model):
    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Pendente'
        ACEITA = 'aceita', 'Aceita'
        RECUSADA = 'recusada', 'Recusada'
        CANCELADA = 'cancelada', 'Cancelada'

    ATIVAS = (Status.PENDENTE, Status.ACEITA)

    carona = models.ForeignKey(
        Carona,
        on_delete=models.CASCADE,
        related_name='reservas',
    )
    passageiro = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reservas',
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDENTE,
    )
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['criada_em']
        constraints = [
            models.UniqueConstraint(
                fields=['carona', 'passageiro'],
                condition=models.Q(status__in=['pendente', 'aceita']),
                name='reserva_ativa_unica_por_carona',
            ),
        ]

    def __str__(self):
        return f'{self.passageiro} em {self.carona} ({self.get_status_display()})'

    @property
    def cancelavel(self):
        return (self.status in self.ATIVAS and self.carona.aberta
                and self.carona.data_hora > timezone.now())

