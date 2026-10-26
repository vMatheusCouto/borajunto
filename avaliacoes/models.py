from django.conf import settings
from django.db import models
from django.db.models import Avg, Count


class AvaliacaoQuerySet(models.QuerySet):
    def validas(self):
        return self.filter(removida=False)

    def reputacao(self, usuario):
        """Média e quantidade das avaliações válidas recebidas (RF25, RN21)."""
        return self.validas().filter(avaliado=usuario).aggregate(
            media=Avg('nota'), quantidade=Count('id'))


class Avaliacao(models.Model):
    """Nota de um participante a outro em uma carona concluída (RF24, RN19-RN20)."""

    carona = models.ForeignKey(
        'caronas.Carona',
        on_delete=models.CASCADE,
        related_name='avaliacoes',
    )
    avaliador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='avaliacoes_feitas',
    )
    avaliado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='avaliacoes_recebidas',
    )
    nota = models.PositiveSmallIntegerField()
    # Avaliações removidas pela moderação saem da reputação (RN21).
    removida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    objects = AvaliacaoQuerySet.as_manager()

    class Meta:
        ordering = ['-criada_em']
        verbose_name = 'avaliação'
        verbose_name_plural = 'avaliações'
        constraints = [
            # Na mesma carona, a nova nota substitui a anterior (RN20).
            models.UniqueConstraint(
                fields=['carona', 'avaliador', 'avaliado'],
                name='avaliacao_unica_por_carona',
            ),
            models.CheckConstraint(
                condition=models.Q(nota__gte=1, nota__lte=5),
                name='avaliacao_nota_de_1_a_5',
            ),
            models.CheckConstraint(  # RN19
                condition=~models.Q(avaliador=models.F('avaliado')),
                name='avaliacao_sem_autoavaliacao',
            ),
        ]

    def __str__(self):
        return f'{self.avaliador} → {self.avaliado}: {self.nota}★'
