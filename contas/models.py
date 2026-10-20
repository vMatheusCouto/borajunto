from django.conf import settings
from django.db import models


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
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.usuario.get_full_name() or self.matricula} ({self.matricula})'
