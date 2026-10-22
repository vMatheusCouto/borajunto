from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from caronas.models import Carona

from .models import Notificacao


class NotificacaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user('ana')
        cls.carona = Carona.objects.create(
            motorista=cls.usuario, origem='Centro', destino='IFRN', ponto_encontro='Praça',
            data_hora=timezone.now() + timedelta(days=1), vagas=3)

    def test_um_lembrete_por_carona(self):  # RF22
        Notificacao.objects.create(destinatario=self.usuario, carona=self.carona,
                                   tipo=Notificacao.Tipo.LEMBRETE, mensagem='Sai em 60 min')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Notificacao.objects.create(destinatario=self.usuario, carona=self.carona,
                                       tipo=Notificacao.Tipo.LEMBRETE, mensagem='De novo')

    def test_notificacao_sobrevive_a_carona(self):  # UC07 E1
        notificacao = Notificacao.objects.create(
            destinatario=self.usuario, carona=self.carona,
            tipo=Notificacao.Tipo.CANCELAMENTO, mensagem='Carona cancelada')
        self.carona.delete()
        notificacao.refresh_from_db()
        self.assertIsNone(notificacao.carona)
        self.assertFalse(notificacao.lida)
