from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from .models import Carona, Reserva


class ReservaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        motorista = User.objects.create_user('motorista')
        cls.passageiro = User.objects.create_user('passageiro')
        cls.carona = Carona.objects.create(
            motorista=motorista, origem='Centro', destino='IFRN', ponto_encontro='Praça',
            data_hora=timezone.now() + timedelta(days=1), vagas=3)

    def test_nova_solicitacao_comeca_pendente(self):  # RN08
        reserva = Reserva.objects.create(carona=self.carona, passageiro=self.passageiro)
        self.assertEqual(reserva.status, Reserva.Status.PENDENTE)

    def test_uma_solicitacao_ativa_por_carona(self):  # RN10
        Reserva.objects.create(carona=self.carona, passageiro=self.passageiro)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reserva.objects.create(carona=self.carona, passageiro=self.passageiro)

    def test_pode_solicitar_de_novo_apos_cancelar(self):
        Reserva.objects.create(carona=self.carona, passageiro=self.passageiro,
                               status=Reserva.Status.CANCELADA)
        Reserva.objects.create(carona=self.carona, passageiro=self.passageiro)
        self.assertEqual(self.carona.reservas.count(), 2)
