from django.conf import settings
from django.db import models


class Denuncia(models.Model):
    """Relato de um estudante sobre um usuário, uma carona ou uma avaliação (RF26)."""

    class Motivo(models.TextChoices):
        CONDUTA = 'conduta', 'Conduta inadequada'
        AUSENCIA = 'ausencia', 'Não compareceu'
        INFORMACAO_FALSA = 'informacao_falsa', 'Informação falsa'
        SEGURANCA = 'seguranca', 'Risco à segurança'
        OUTRO = 'outro', 'Outro'

    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Pendente'
        PROCEDENTE = 'procedente', 'Procedente'
        IMPROCEDENTE = 'improcedente', 'Improcedente'

    denunciante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='denuncias_feitas',
    )
    # Exatamente um alvo; PROTECT preserva o registro para a moderação.
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='denuncias_recebidas',
    )
    carona = models.ForeignKey(
        'caronas.Carona',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='denuncias',
    )
    avaliacao = models.ForeignKey(
        'avaliacoes.Avaliacao',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='denuncias',
    )
    motivo = models.CharField(max_length=16, choices=Motivo.choices)
    descricao = models.TextField()
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDENTE,
    )
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criada_em']
        verbose_name = 'denúncia'
        verbose_name_plural = 'denúncias'
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(usuario__isnull=False, carona__isnull=True, avaliacao__isnull=True)
                    | models.Q(usuario__isnull=True, carona__isnull=False, avaliacao__isnull=True)
                    | models.Q(usuario__isnull=True, carona__isnull=True, avaliacao__isnull=False)
                ),
                name='denuncia_com_um_unico_alvo',
            ),
        ]

    @property
    def alvo(self):
        return self.usuario or self.carona or self.avaliacao

    def __str__(self):
        return f'{self.get_motivo_display()}: {self.alvo} ({self.get_status_display()})'


class DecisaoModeracao(models.Model):
    """Registro de auditoria de cada decisão tomada sobre uma denúncia (RF27, RN22, RNF12)."""

    class Acao(models.TextChoices):
        NENHUMA = 'nenhuma', 'Nenhuma ação'
        OCULTAR_CONTEUDO = 'ocultar_conteudo', 'Ocultar conteúdo'
        RESTRINGIR_CONTA = 'restringir_conta', 'Restringir conta'

    denuncia = models.ForeignKey(
        Denuncia,
        on_delete=models.PROTECT,
        related_name='decisoes',
    )
    administrador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='decisoes_moderacao',
    )
    resultado = models.CharField(
        max_length=12,
        choices=[c for c in Denuncia.Status.choices if c[0] != Denuncia.Status.PENDENTE],
    )
    acao = models.CharField(max_length=16, choices=Acao.choices, default=Acao.NENHUMA)
    justificativa = models.TextField()
    decidida_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-decidida_em']
        verbose_name = 'decisão de moderação'
        verbose_name_plural = 'decisões de moderação'
        constraints = [
            models.CheckConstraint(  # RN22
                condition=~models.Q(justificativa=''),
                name='decisao_com_justificativa',
            ),
        ]

    def __str__(self):
        return f'{self.get_resultado_display()} por {self.administrador}'
