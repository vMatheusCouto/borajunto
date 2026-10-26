from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
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


class PublicarCaronaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.motorista = get_user_model().objects.create_user('motorista')

    def setUp(self):
        self.client.force_login(self.motorista)
        self.amanha = timezone.localtime() + timedelta(days=1)

    def trajeto(self, **campos):
        dados = {'origem': 'Pau dos Ferros', 'destino': 'Campus Mossoró', 'ponto_encontro': 'Praça central',
                 'data': self.amanha.date().isoformat(), 'horario': '06:30', **campos}
        return self.client.post(reverse('caronas:oferecer'), dados)

    def test_publica_em_dois_passos(self):
        self.assertRedirects(self.trajeto(), reverse('caronas:oferecer_vagas'))
        resposta = self.client.post(reverse('caronas:oferecer_vagas'), {'vagas': 2, 'observacoes': 'Sem bagagem.'})
        self.assertRedirects(resposta, reverse('caronas:viagens'))
        carona = Carona.objects.get()
        self.assertEqual((carona.motorista, carona.vagas, carona.status),
                         (self.motorista, 2, Carona.Status.PUBLICADA))
        self.assertEqual(timezone.localtime(carona.data_hora).strftime('%H:%M'), '06:30')
        self.assertNotIn('carona_rascunho', self.client.session)

    def test_data_passada_nao_avanca(self):
        resposta = self.trajeto(data=(self.amanha - timedelta(days=3)).date().isoformat())
        self.assertContains(resposta, 'ainda não passaram')
        self.assertNotIn('carona_rascunho', self.client.session)

    def test_vagas_entre_1_e_o_maximo(self):
        self.trajeto()
        for vagas in (0, 7):
            with self.subTest(vagas=vagas):
                self.client.post(reverse('caronas:oferecer_vagas'), {'vagas': vagas})
        self.assertFalse(Carona.objects.exists())

    def test_passo_2_sem_passo_1_volta_ao_inicio(self):
        self.assertRedirects(self.client.get(reverse('caronas:oferecer_vagas')), reverse('caronas:oferecer'))


class DecidirSolicitacaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.motorista = User.objects.create_user('motorista')
        cls.ana = User.objects.create_user('ana', first_name='Ana')
        cls.lucas = User.objects.create_user('lucas', first_name='Lucas')
        cls.carona = Carona.objects.create(
            motorista=cls.motorista, origem='Centro', destino='IFRN', ponto_encontro='Praça',
            data_hora=timezone.now() + timedelta(days=1), vagas=1)

    def setUp(self):
        self.client.force_login(self.motorista)
        self.da_ana = Reserva.objects.create(carona=self.carona, passageiro=self.ana)
        self.do_lucas = Reserva.objects.create(carona=self.carona, passageiro=self.lucas)

    def decidir(self, reserva, decisao):
        return self.client.post(reverse(f'caronas:{decisao}', args=[reserva.pk]))

    def test_aceitar_ultima_vaga_lota_a_carona_e_avisa(self):
        self.assertRedirects(self.decidir(self.da_ana, 'aceitar'), reverse('caronas:viagens'))
        self.da_ana.refresh_from_db()
        self.carona.refresh_from_db()
        self.assertEqual(self.da_ana.status, Reserva.Status.ACEITA)
        self.assertEqual(self.carona.status, Carona.Status.LOTADA)
        self.assertTrue(Notificacao.objects.filter(destinatario=self.ana, tipo='decisao').exists())

    def test_nao_aceita_alem_das_vagas(self):
        self.decidir(self.da_ana, 'aceitar')
        self.decidir(self.do_lucas, 'aceitar')
        self.do_lucas.refresh_from_db()
        self.assertEqual(self.do_lucas.status, Reserva.Status.PENDENTE)

    def test_recusar(self):
        self.decidir(self.da_ana, 'recusar')
        self.da_ana.refresh_from_db()
        self.assertEqual(self.da_ana.status, Reserva.Status.RECUSADA)
        with self.assertRaises(ValidationError):
            self.da_ana.aceitar()

    def test_somente_o_motorista_decide(self):
        self.client.force_login(self.lucas)
        self.assertEqual(self.decidir(self.da_ana, 'aceitar').status_code, 404)
        self.assertEqual(self.client.get(reverse('caronas:aceitar', args=[self.da_ana.pk])).status_code, 405)

    def test_viagens_lista_pendentes_e_solicitadas(self):
        resposta = self.client.get(reverse('caronas:viagens'))
        self.assertEqual([r.passageiro for r in resposta.context['caronas'][0].pendentes], [self.ana, self.lucas])
        self.client.force_login(self.ana)
        resposta = self.client.get(reverse('caronas:viagens'), {'aba': 'solicitei'})
        self.assertContains(resposta, 'Centro → IFRN')
        self.assertContains(resposta, 'Pendente')
