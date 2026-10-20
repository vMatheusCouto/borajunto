from django.conf import settings
from django.db import models


class Carona(models.Model):
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
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PUBLICADA,
    )
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['data_hora']

    def __str__(self):
        return f'{self.origem} → {self.destino} ({self.data_hora:%d/%m/%Y %H:%M})'
