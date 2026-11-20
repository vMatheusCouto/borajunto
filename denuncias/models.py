from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction


class Denuncia(models.Model):
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

    @property
    def responsavel(self):
        if self.usuario_id:
            return self.usuario
        if self.carona_id:
            return self.carona.motorista
        return self.avaliacao.avaliador

    def __str__(self):
        return f'{self.get_motivo_display()}: {self.alvo} ({self.get_status_display()})'


class DecisaoModeracao(models.Model):
    class Acao(models.TextChoices):
        NENHUMA = 'nenhuma', 'Nenhuma ação'
        SUSPENDER_CONTA = 'suspender_conta', 'Suspender conta'
        CANCELAR_CARONA = 'cancelar_carona', 'Cancelar carona'
        REMOVER_AVALIACAO = 'remover_avaliacao', 'Remover avaliação'

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
    acao = models.CharField(max_length=20, choices=Acao.choices, default=Acao.NENHUMA,
                            verbose_name='ação')
    dias_suspensao = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name='dias de suspensão',
        help_text='Só para "Suspender conta". Deixe vazio para suspender até reativação manual.',
    )
    justificativa = models.TextField()
    decidida_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-decidida_em']
        verbose_name = 'decisão de moderação'
        verbose_name_plural = 'decisões de moderação'
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(justificativa=''),
                name='decisao_com_justificativa',
            ),
            models.CheckConstraint(
                condition=models.Q(resultado='procedente') | models.Q(acao='nenhuma'),
                name='decisao_improcedente_sem_acao',
            ),
            models.CheckConstraint(
                condition=models.Q(dias_suspensao__isnull=True) | models.Q(acao='suspender_conta'),
                name='decisao_dias_so_com_suspensao',
            ),
        ]

    def clean(self):
        if not self.denuncia_id:
            return
        denuncia = self.denuncia
        if self.resultado == Denuncia.Status.IMPROCEDENTE and self.acao != self.Acao.NENHUMA:
            raise ValidationError({'acao': 'Denúncia improcedente não pode ter ação.'})
        if self.dias_suspensao and self.acao != self.Acao.SUSPENDER_CONTA:
            raise ValidationError(
                {'dias_suspensao': 'Dias de suspensão só valem para "Suspender conta".'})
        if self.acao == self.Acao.CANCELAR_CARONA:
            if not denuncia.carona_id:
                raise ValidationError({'acao': 'Só dá para cancelar carona se o alvo for uma carona.'})
            if not denuncia.carona.aberta:
                raise ValidationError(
                    {'acao': 'Essa carona já começou, terminou ou foi cancelada.'})
        if self.acao == self.Acao.REMOVER_AVALIACAO and not denuncia.avaliacao_id:
            raise ValidationError(
                {'acao': 'Só dá para remover avaliação se o alvo for uma avaliação.'})
        if self.acao == self.Acao.SUSPENDER_CONTA:
            responsavel = denuncia.responsavel
            if responsavel.is_staff:
                raise ValidationError({'acao': 'Contas da administração não podem ser suspensas.'})
            if self.dias_suspensao and not hasattr(responsavel, 'perfil'):
                raise ValidationError(
                    {'dias_suspensao': 'Essa conta não tem perfil; use a suspensão sem prazo.'})

    def save(self, *args, **kwargs):
        nova = self._state.adding
        with transaction.atomic():
            super().save(*args, **kwargs)
            if nova:
                from .moderacao import aplicar_decisao
                aplicar_decisao(self)

    def __str__(self):
        return f'{self.get_resultado_display()} por {self.administrador}'
