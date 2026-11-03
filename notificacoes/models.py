from django.conf import settings
from django.db import models


class Notificacao(models.Model):
    class Tipo(models.TextChoices):
        SOLICITACAO = 'solicitacao', 'Nova solicitação'
        DECISAO = 'decisao', 'Decisão do motorista'
        ALTERACAO = 'alteracao', 'Alteração da carona'
        CANCELAMENTO = 'cancelamento', 'Cancelamento'
        LEMBRETE = 'lembrete', 'Lembrete'

    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notificacoes',
    )
    carona = models.ForeignKey(
        'caronas.Carona',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notificacoes',
    )
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    mensagem = models.CharField(max_length=255)
    lida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criada_em']
        verbose_name = 'notificação'
        verbose_name_plural = 'notificações'
        constraints = [
            models.UniqueConstraint(
                fields=['destinatario', 'carona'],
                condition=models.Q(tipo='lembrete'),
                name='lembrete_unico_por_carona',
            ),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} para {self.destinatario}'
