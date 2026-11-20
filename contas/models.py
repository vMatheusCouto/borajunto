from django.conf import settings
from django.db import models
from django.urls import reverse


class Perfil(models.Model):
    """Dados institucionais importados do SUAP a cada login (RF02, RN02)."""

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil',
    )
    matricula = models.CharField(max_length=30, unique=True)
    curso = models.CharField(max_length=255, blank=True)
    campus = models.CharField(max_length=50, blank=True)
    foto_url = models.CharField(max_length=500, blank=True)
    foto = models.BinaryField(null=True, editable=False)
    foto_atualizada_em = models.DateTimeField(null=True, editable=False)
    apresentacao = models.CharField('apresentação', max_length=280, blank=True)
    receber_lembretes = models.BooleanField('receber lembretes', default=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    @property
    def foto_enviada_url(self):
        if not self.foto_atualizada_em:
            return ''
        versao = int(self.foto_atualizada_em.timestamp())
        return f"{reverse('contas:foto', args=[self.usuario_id])}?v={versao}"

    @property
    def foto_exibida_url(self):
        return self.foto_enviada_url or self.foto_url

    def __str__(self):
        return f'{self.usuario.get_full_name() or self.matricula} ({self.matricula})'
