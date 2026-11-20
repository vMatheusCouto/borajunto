from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from avaliacoes.models import Avaliacao
from caronas.models import Carona, Reserva
from notificacoes.models import Notificacao

from .models import Denuncia

User = get_user_model()


class RegistrarDenunciaTests(TestCase):
    """UC09 - Registrar denúncia (RF26, RN22, RNF06)."""

    @classmethod
    def setUpTestData(cls):
        cls.eu = User.objects.create_user('eu', first_name='Mateus', last_name='Silva')
        cls.bruno = User.objects.create_user('bruno', first_name='Bruno', last_name='Tavares')
        cls.ana = User.objects.create_user('ana', first_name='Ana', last_name='Lima')
        cls.carona = Carona.objects.create(
            motorista=cls.bruno, origem='Umarizal', destino='Mossoró',
            ponto_encontro='Praça da matriz', data_hora=timezone.now() - timedelta(days=1),
            vagas=3, status=Carona.Status.CONCLUIDA)
        Reserva.objects.create(carona=cls.carona, passageiro=cls.eu, status=Reserva.Status.ACEITA)
        cls.minha_carona = Carona.objects.create(
            motorista=cls.eu, origem='Pau dos Ferros', destino='Mossoró',
            ponto_encontro='IFRN', data_hora=timezone.now() + timedelta(days=1), vagas=2)
        cls.recebida = Avaliacao.objects.create(
            carona=cls.carona, avaliador=cls.bruno, avaliado=cls.eu, nota=1)
        cls.de_outro = Avaliacao.objects.create(
            carona=cls.carona, avaliador=cls.eu, avaliado=cls.bruno, nota=5)

    def setUp(self):
        self.client.force_login(self.eu)

    def enviar(self, url, motivo='ausencia', descricao='Não apareceu nem avisou.', follow=False,
               **extra):
        return self.client.post(url, {'motivo': motivo, 'descricao': descricao, **extra},
                                follow=follow)

    def test_exige_login(self):
        self.client.logout()
        resposta = self.client.get(reverse('denuncias:carona', args=[self.carona.pk]))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('contas:entrar'), resposta['Location'])

    def test_tela_mostra_o_alvo_e_os_motivos_do_prototipo(self):
        resposta = self.client.get(reverse('denuncias:carona', args=[self.carona.pk]))
        self.assertContains(resposta, 'Denunciar um problema')
        self.assertContains(resposta, 'Bruno Tavares · Umarizal → Mossoró')
        for rotulo in ('Não compareceu', 'Comportamento inadequado', 'Cobrança indevida',
                       'Perfil falso', 'Outro'):
            self.assertContains(resposta, rotulo)
        self.assertNotContains(resposta, 'Risco à segurança')

    def test_registra_denuncia_de_carona_como_pendente(self):
        resposta = self.enviar(reverse('denuncias:carona', args=[self.carona.pk]))
        self.assertRedirects(resposta, reverse('contas:perfil'), fetch_redirect_response=False)
        denuncia = Denuncia.objects.get()
        self.assertEqual(denuncia.carona, self.carona)
        self.assertIsNone(denuncia.usuario)
        self.assertEqual(denuncia.denunciante, self.eu)
        self.assertEqual(denuncia.status, Denuncia.Status.PENDENTE)
        self.assertEqual(denuncia.motivo, Denuncia.Motivo.AUSENCIA)

    def test_registra_denuncia_de_usuario(self):
        self.enviar(reverse('denuncias:usuario', args=[self.bruno.pk]), motivo='perfil_falso')
        self.assertEqual(Denuncia.objects.get().usuario, self.bruno)

    def test_registra_denuncia_de_avaliacao_recebida(self):
        self.enviar(reverse('denuncias:avaliacao', args=[self.recebida.pk]), motivo='outro')
        self.assertEqual(Denuncia.objects.get().avaliacao, self.recebida)

    def test_confirma_o_envio(self):
        resposta = self.enviar(reverse('denuncias:usuario', args=[self.bruno.pk]), follow=True)
        self.assertContains(resposta, 'Denúncia enviada')

    def test_motivo_e_descricao_sao_obrigatorios(self):
        url = reverse('denuncias:carona', args=[self.carona.pk])
        resposta = self.enviar(url, motivo='', descricao='   ')
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Escolha o tipo do problema.')
        self.assertContains(resposta, 'Descreva o problema.')
        self.assertFalse(Denuncia.objects.exists())

    def test_nao_aceita_motivo_fora_da_tela(self):
        self.enviar(reverse('denuncias:carona', args=[self.carona.pk]), motivo='seguranca')
        self.assertFalse(Denuncia.objects.exists())

    def test_nao_denuncia_a_si_mesmo(self):
        resposta = self.enviar(reverse('denuncias:usuario', args=[self.eu.pk]))
        self.assertEqual(resposta.status_code, 404)

    def test_nao_denuncia_a_propria_carona(self):
        resposta = self.enviar(reverse('denuncias:carona', args=[self.minha_carona.pk]))
        self.assertEqual(resposta.status_code, 404)

    def test_so_denuncia_avaliacao_recebida(self):
        resposta = self.enviar(reverse('denuncias:avaliacao', args=[self.de_outro.pk]))
        self.assertEqual(resposta.status_code, 404)
        self.assertFalse(Denuncia.objects.exists())

    def test_nao_repete_denuncia_pendente_sobre_o_mesmo_alvo(self):
        url = reverse('denuncias:usuario', args=[self.bruno.pk])
        self.enviar(url)
        resposta = self.enviar(url, follow=True)
        self.assertEqual(Denuncia.objects.count(), 1)
        self.assertContains(resposta, 'Você já denunciou isso')

    def test_volta_para_o_next_interno_e_ignora_externo(self):
        url = reverse('denuncias:usuario', args=[self.bruno.pk])
        detalhe = reverse('caronas:detalhe', args=[self.carona.pk])
        resposta = self.enviar(url, next=detalhe)
        self.assertRedirects(resposta, detalhe, fetch_redirect_response=False)
        resposta = self.enviar(reverse('denuncias:carona', args=[self.carona.pk]),
                               next='https://exemplo.com/')
        self.assertRedirects(resposta, reverse('contas:perfil'), fetch_redirect_response=False)

    def test_nao_avisa_a_pessoa_denunciada(self):
        self.enviar(reverse('denuncias:usuario', args=[self.bruno.pk]))
        self.assertFalse(Notificacao.objects.filter(destinatario=self.bruno).exists())


class EscolherAlvoTests(TestCase):
    """Entrada pelo perfil: escolher a carona ou a pessoa a denunciar."""

    @classmethod
    def setUpTestData(cls):
        cls.eu = User.objects.create_user('eu', first_name='Mateus', last_name='Silva')
        cls.bruno = User.objects.create_user('bruno', first_name='Bruno', last_name='Tavares')
        cls.carona = Carona.objects.create(
            motorista=cls.bruno, origem='Umarizal', destino='Mossoró',
            ponto_encontro='Praça', data_hora=timezone.now() - timedelta(days=1),
            vagas=3, status=Carona.Status.CONCLUIDA)
        Reserva.objects.create(carona=cls.carona, passageiro=cls.eu, status=Reserva.Status.ACEITA)
        cls.alheia = Carona.objects.create(
            motorista=cls.bruno, origem='Apodi', destino='Natal', ponto_encontro='Praça',
            data_hora=timezone.now() + timedelta(days=1), vagas=3)

    def test_lista_caronas_do_estudante_e_seus_participantes(self):
        self.client.force_login(self.eu)
        resposta = self.client.get(reverse('denuncias:escolher'))
        self.assertContains(resposta, reverse('denuncias:carona', args=[self.carona.pk]))
        self.assertContains(resposta, reverse('denuncias:usuario', args=[self.bruno.pk]))
        self.assertNotContains(resposta, reverse('denuncias:usuario', args=[self.eu.pk]))
        self.assertNotContains(resposta, 'Apodi')

    def test_perfil_leva_a_denuncia(self):
        self.client.force_login(self.eu)
        resposta = self.client.get(reverse('contas:perfil'))
        self.assertContains(resposta, reverse('denuncias:escolher'))

    def test_detalhe_mostra_denunciar_carona_so_para_quem_nao_e_motorista(self):
        url = reverse('caronas:detalhe', args=[self.carona.pk])
        link = reverse('denuncias:carona', args=[self.carona.pk])
        self.client.force_login(self.eu)
        self.assertContains(self.client.get(url), link)
        self.client.force_login(self.bruno)
        self.assertNotContains(self.client.get(url), link)
