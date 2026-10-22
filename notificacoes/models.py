from django.conf import settings
from django.db import models


class Notificacao(models.Model):
    """Aviso interno sobre solicitações, decisões, alterações e lembretes (RF21, RF22)."""

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
    # A mensagem continua na central mesmo se a carona deixar de existir (UC07 E1).
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
            # Um único lembrete de 60 minutos por pessoa e carona (RF22, RN16).
            models.UniqueConstraint(
                fields=['destinatario', 'carona'],
                condition=models.Q(tipo='lembrete'),
                name='lembrete_unico_por_carona',
            ),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} para {self.destinatario}'
