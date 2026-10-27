from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from notificacoes.models import Notificacao

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



class SolicitarVagaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.motorista = User.objects.create_user('motorista')
        cls.passageiro = User.objects.create_user('passageiro')
        cls.carona = Carona.objects.create(
            motorista=cls.motorista, origem='Centro', destino='IFRN', ponto_encontro='Praça',
            data_hora=timezone.now() + timedelta(days=1), vagas=1)

    def setUp(self):
        self.client.force_login(self.passageiro)

    def solicitar(self, carona=None):
        return self.client.post(reverse('caronas:solicitar', args=[(carona or self.carona).pk]))

    def test_detalhe_mostra_botao_de_solicitar(self):
        resposta = self.client.get(reverse('caronas:detalhe', args=[self.carona.pk]))
        self.assertContains(resposta, 'Solicitar vaga')

    def test_solicitacao_fica_pendente_e_avisa_o_motorista(self):  # UC05, RN08
        self.solicitar()
        reserva = Reserva.objects.get(passageiro=self.passageiro)
        self.assertEqual(reserva.status, Reserva.Status.PENDENTE)
        self.assertTrue(Notificacao.objects.filter(destinatario=self.motorista, tipo='solicitacao').exists())

    def test_motorista_nao_solicita_a_propria_carona(self):  # RN09
        self.client.force_login(self.motorista)
        self.solicitar()
        self.assertFalse(Reserva.objects.exists())

    def test_nao_duplica_solicitacao(self):  # RN10
        self.solicitar()
        self.solicitar()
        self.assertEqual(Reserva.objects.count(), 1)

    def test_carona_lotada_nao_recebe_solicitacao(self):  # RN07
        outro = get_user_model().objects.create_user('outro')
        Reserva.objects.create(carona=self.carona, passageiro=outro, status=Reserva.Status.ACEITA)
        self.solicitar()
        self.assertFalse(Reserva.objects.filter(passageiro=self.passageiro).exists())

    def test_impede_reservas_com_saidas_a_menos_de_60_minutos(self):  # RN10, UC05 E3
        proxima = Carona.objects.create(
            motorista=self.motorista, origem='Bairro', destino='IFRN', ponto_encontro='Escola',
            data_hora=self.carona.data_hora + timedelta(minutes=30), vagas=2)
        self.solicitar()
        self.solicitar(proxima)
        self.assertFalse(Reserva.objects.filter(carona=proxima).exists())

    def test_cancelar_reserva_confirmada_devolve_a_vaga(self):  # RN12, UC05 A2
        reserva = Reserva.objects.create(carona=self.carona, passageiro=self.passageiro,
                                         status=Reserva.Status.ACEITA)
        Carona.objects.filter(pk=self.carona.pk).update(status=Carona.Status.LOTADA)
        self.client.post(reverse('caronas:cancelar', args=[reserva.pk]))
        reserva.refresh_from_db()
        self.carona.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.CANCELADA)
        self.assertEqual(self.carona.status, Carona.Status.PUBLICADA)
        self.assertTrue(Carona.objects.disponiveis().filter(pk=self.carona.pk).exists())
