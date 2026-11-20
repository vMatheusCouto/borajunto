from django.conf import settings
from django.db import models
from django.utils import timezone


class Perfil(models.Model):
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
    suspensa_ate = models.DateTimeField(null=True, blank=True, verbose_name='suspensa até')

    def __str__(self):
        return f'{self.usuario.get_full_name() or self.matricula} ({self.matricula})'


def conta_suspensa(usuario):
    if not usuario.is_active:
        return True
    perfil = getattr(usuario, 'perfil', None)
    return bool(perfil and perfil.suspensa_ate and perfil.suspensa_ate > timezone.now())
