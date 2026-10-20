import logging

import suapy
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.db import transaction

from .models import Perfil

logger = logging.getLogger(__name__)

ERRO_VINCULO = 'Sua matrícula não tem vínculo de aluno ativo no SUAP.'
ERRO_SUAP = 'Não foi possível falar com o SUAP agora. Tente novamente em alguns minutos.'


class SuapBackend(BaseBackend):
    """Autentica pela matrícula e senha do SUAP (RF01).

    A senha só é repassada ao SUAP pelo suapy; o BoraJunto não a guarda.
    Quando o login falha por um motivo que a pessoa precisa saber, a
    mensagem fica em ``request.erro_suap`` para o formulário exibir.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        try:
            perfil_suap = suapy.autenticar(
                username.strip(), password, url_base=settings.SUAP_URL)
        except suapy.SuapAuthError:
            return None
        except suapy.SuapError:
            logger.warning('Falha ao acessar o SUAP durante o login.', exc_info=True)
            self._registrar_erro(request, ERRO_SUAP)
            return None
        if not perfil_suap.aluno_ativo:  # RN01
            self._registrar_erro(request, ERRO_VINCULO)
            return None
        return self._sincronizar(perfil_suap)

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    @staticmethod
    def _registrar_erro(request, mensagem):
        if request is not None:
            request.erro_suap = mensagem

    @staticmethod
    @transaction.atomic
    def _sincronizar(perfil_suap):
        """Cria ou atualiza usuário e perfil com os dados do SUAP (RF02)."""
        User = get_user_model()
        user, criado = User.objects.get_or_create(username=perfil_suap.matricula)
        if criado:
            user.set_unusable_password()
        nome, _, sobrenome = perfil_suap.nome.partition(' ')
        user.first_name = nome[:150]
        user.last_name = sobrenome[:150]
        user.email = perfil_suap.email
        user.save()
        Perfil.objects.update_or_create(
            usuario=user,
            defaults={
                'matricula': perfil_suap.matricula,
                'curso': perfil_suap.vinculo_aluno_ativo.curso or '',
                'campus': perfil_suap.campus,
                'foto_url': perfil_suap.foto,
            },
        )
        return user
