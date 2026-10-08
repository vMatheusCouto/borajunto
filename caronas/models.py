from django.conf import settings
from django.db import models


class Carona(models.Model):
    class Status(models.TextChoices):
        ABERTA = 'aberta', 'Aberta'
        CANCELADA = 'cancelada', 'Cancelada'
        CONCLUIDA = 'concluida', 'Concluída'

    motorista = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='caronas',
    )
    origem = models.CharField(max_length=255)
    destino = models.CharField(max_length=255)
    data_hora = models.DateTimeField()
    vagas = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ABERTA,
    )
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['data_hora']

    def __str__(self):
        return f'{self.origem} → {self.destino} ({self.data_hora:%d/%m/%Y %H:%M})'
