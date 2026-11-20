from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from avaliacoes.models import Avaliacao
from caronas.models import Carona, Reserva
from contas.backends import SuapBackend
from contas.forms import EntrarForm
from contas.models import Perfil, conta_suspensa
from notificacoes.models import Notificacao

from .models import DecisaoModeracao, Denuncia

Acao = DecisaoModeracao.Acao


class ModeracaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser('admin')
        cls.ana = User.objects.create_user('ana', first_name='Ana')
        cls.lucas = User.objects.create_user('lucas', first_name='Lucas')
        cls.bruno = User.objects.create_user('bruno', first_name='Bruno')
        for usuario in (cls.ana, cls.lucas, cls.bruno):
            Perfil.objects.create(usuario=usuario, matricula=usuario.username)

    def setUp(self):
        agora = timezone.now()
        self.carona = self.criar_carona(self.lucas, agora + timedelta(days=2))
        Reserva.objects.create(carona=self.carona, passageiro=self.ana, status=Reserva.Status.ACEITA)

    def criar_carona(self, motorista, data_hora, vagas=1):
        return Carona.objects.create(motorista=motorista, origem='Natal', destino='Parnamirim',
                                     ponto_encontro='Portão', data_hora=data_hora, vagas=vagas)

    def denunciar(self, **alvo):
        return Denuncia.objects.create(denunciante=self.ana, motivo=Denuncia.Motivo.CONDUTA,
                                       descricao='Foi grosseiro.', **alvo)

    def decidir(self, denuncia, acao=Acao.NENHUMA, resultado=Denuncia.Status.PROCEDENTE, dias=None):
        decisao = DecisaoModeracao(denuncia=denuncia, administrador=self.admin, resultado=resultado,
                                   acao=acao, dias_suspensao=dias, justificativa='Analisado.')
        decisao.full_clean()
        decisao.save()
        return decisao

    def avisos(self, usuario, tipo=Notificacao.Tipo.MODERACAO):
        return list(Notificacao.objects.filter(destinatario=usuario, tipo=tipo)
                    .values_list('mensagem', flat=True))

    def test_status_segue_a_decisao(self):
        denuncia = self.denunciar(usuario=self.lucas)
        self.decidir(denuncia, resultado=Denuncia.Status.IMPROCEDENTE)
        denuncia.refresh_from_db()
        self.assertEqual(denuncia.status, Denuncia.Status.IMPROCEDENTE)
        self.decidir(denuncia, resultado=Denuncia.Status.PROCEDENTE)
        denuncia.refresh_from_db()
        self.assertEqual(denuncia.status, Denuncia.Status.PROCEDENTE)

    def test_improcedente_avisa_so_o_denunciante(self):
        self.decidir(self.denunciar(usuario=self.lucas), resultado=Denuncia.Status.IMPROCEDENTE)
        self.assertEqual(self.avisos(self.ana),
                         ['Sua denúncia por "Conduta inadequada" foi analisada e considerada improcedente.'])
        self.assertEqual(self.avisos(self.lucas), [])
        self.lucas.refresh_from_db()
        self.assertTrue(self.lucas.is_active)

    def test_cancelar_carona(self):
        self.decidir(self.denunciar(carona=self.carona), Acao.CANCELAR_CARONA)
        self.carona.refresh_from_db()
        self.assertEqual(self.carona.status, Carona.Status.CANCELADA)
        self.assertEqual(self.carona.motivo_cancelamento, 'Cancelada pela moderação.')
        self.assertFalse(self.carona.reservas.filter(status__in=Reserva.ATIVAS).exists())
        self.assertEqual(self.avisos(self.ana, Notificacao.Tipo.CANCELAMENTO),
                         ['A carona Natal → Parnamirim foi cancelada pela moderação.'])
        self.assertIn('Sua carona Natal → Parnamirim foi cancelada pela moderação',
                      self.avisos(self.lucas)[0])
        self.lucas.refresh_from_db()
        self.assertTrue(self.lucas.is_active)

    def test_nao_cancela_carona_ja_iniciada(self):
        self.carona.status = Carona.Status.EM_ANDAMENTO
        self.carona.save()
        with self.assertRaises(ValidationError):
            self.decidir(self.denunciar(carona=self.carona), Acao.CANCELAR_CARONA)

    def test_remover_avaliacao(self):
        avaliacao = Avaliacao.objects.create(carona=self.carona, avaliador=self.ana,
                                             avaliado=self.lucas, nota=1)
        denuncia = Denuncia.objects.create(denunciante=self.lucas, motivo=Denuncia.Motivo.OUTRO,
                                           descricao='Nota injusta.', avaliacao=avaliacao)
        self.decidir(denuncia, Acao.REMOVER_AVALIACAO)
        avaliacao.refresh_from_db()
        self.assertTrue(avaliacao.removida)
        self.assertEqual(Avaliacao.objects.reputacao(self.lucas)['quantidade'], 0)
        self.assertIn('Uma avaliação sua foi removida', self.avisos(self.ana)[0])

    def test_suspensao_sem_prazo(self):
        carona_bruno = self.criar_carona(self.bruno, timezone.now() + timedelta(days=30))
        Reserva.objects.create(carona=carona_bruno, passageiro=self.lucas, status=Reserva.Status.ACEITA)
        carona_bruno.atualizar_lotacao()

        self.decidir(self.denunciar(usuario=self.lucas), Acao.SUSPENDER_CONTA)
        self.lucas.refresh_from_db()
        self.assertFalse(self.lucas.is_active)
        self.assertIsNone(SuapBackend().get_user(self.lucas.pk))
        self.carona.refresh_from_db()
        self.assertEqual(self.carona.status, Carona.Status.CANCELADA)
        self.assertEqual(len(self.avisos(self.ana, Notificacao.Tipo.CANCELAMENTO)), 1)
        carona_bruno.refresh_from_db()
        self.assertEqual(carona_bruno.status, Carona.Status.PUBLICADA)
        self.assertFalse(carona_bruno.reservas.filter(status__in=Reserva.ATIVAS).exists())
        self.assertEqual(self.avisos(self.bruno, Notificacao.Tipo.CANCELAMENTO),
                         ['A reserva de Lucas em Natal → Parnamirim foi cancelada pela moderação.'])
        self.assertEqual(self.avisos(self.lucas), ['Sua conta foi suspensa após uma denúncia por "Conduta inadequada".'])

    def test_suspensao_com_prazo(self):
        depois = self.criar_carona(self.lucas, timezone.now() + timedelta(days=10))
        self.decidir(self.denunciar(usuario=self.lucas), Acao.SUSPENDER_CONTA, dias=7)

        self.lucas.refresh_from_db()
        self.assertTrue(self.lucas.is_active)
        fim = self.lucas.perfil.suspensa_ate
        self.assertAlmostEqual(fim, timezone.now() + timedelta(days=7), delta=timedelta(minutes=1))
        self.assertTrue(conta_suspensa(self.lucas))
        self.assertIsNone(SuapBackend().get_user(self.lucas.pk))

        self.carona.refresh_from_db()
        depois.refresh_from_db()
        self.assertEqual(self.carona.status, Carona.Status.CANCELADA)
        self.assertEqual(depois.status, Carona.Status.PUBLICADA)
        self.assertIn('Sua conta foi suspensa até', self.avisos(self.lucas)[0])

        Perfil.objects.filter(usuario=self.lucas).update(suspensa_ate=timezone.now() - timedelta(minutes=1))
        self.assertEqual(SuapBackend().get_user(self.lucas.pk), self.lucas)

    def test_suspender_motorista_pela_denuncia_da_carona(self):
        self.decidir(self.denunciar(carona=self.carona), Acao.SUSPENDER_CONTA)
        self.lucas.refresh_from_db()
        self.assertFalse(self.lucas.is_active)

    def test_login_barrado_com_mensagem(self):
        form = EntrarForm()
        self.decidir(self.denunciar(usuario=self.lucas), Acao.SUSPENDER_CONTA, dias=3)
        self.lucas.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, 'Sua conta está suspensa até'):
            form.confirm_login_allowed(self.lucas)
        self.decidir(self.denunciar(usuario=self.bruno), Acao.SUSPENDER_CONTA)
        self.bruno.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, 'Sua conta foi suspensa pela moderação.'):
            form.confirm_login_allowed(self.bruno)
        form.confirm_login_allowed(self.ana)

    def test_validacoes(self):
        casos = [
            (self.denunciar(usuario=self.lucas), Acao.SUSPENDER_CONTA, Denuncia.Status.IMPROCEDENTE, None),
            (self.denunciar(usuario=self.lucas), Acao.CANCELAR_CARONA, Denuncia.Status.PROCEDENTE, None),
            (self.denunciar(carona=self.carona), Acao.REMOVER_AVALIACAO, Denuncia.Status.PROCEDENTE, None),
            (self.denunciar(carona=self.carona), Acao.CANCELAR_CARONA, Denuncia.Status.PROCEDENTE, 3),
            (self.denunciar(usuario=self.admin), Acao.SUSPENDER_CONTA, Denuncia.Status.PROCEDENTE, None),
        ]
        for denuncia, acao, resultado, dias in casos:
            with self.subTest(acao=acao, resultado=resultado, dias=dias):
                with self.assertRaises(ValidationError):
                    self.decidir(denuncia, acao, resultado, dias)
        self.assertFalse(DecisaoModeracao.objects.exists())

    def test_decisao_pelo_admin(self):
        denuncia = self.denunciar(usuario=self.lucas)
        self.client.force_login(self.admin)
        resposta = self.client.post(f'/admin/denuncias/denuncia/{denuncia.pk}/change/', {
            'decisoes-TOTAL_FORMS': '1', 'decisoes-INITIAL_FORMS': '0',
            'decisoes-MIN_NUM_FORMS': '0', 'decisoes-MAX_NUM_FORMS': '1000',
            'decisoes-0-resultado': 'procedente', 'decisoes-0-acao': 'suspender_conta',
            'decisoes-0-dias_suspensao': '', 'decisoes-0-justificativa': 'Comprovado.',
        })
        self.assertEqual(resposta.status_code, 302)
        decisao = denuncia.decisoes.get()
        self.assertEqual(decisao.administrador, self.admin)
        self.lucas.refresh_from_db()
        self.assertFalse(self.lucas.is_active)

    def test_admin_mostra_erro_de_validacao(self):
        denuncia = self.denunciar(usuario=self.lucas)
        self.client.force_login(self.admin)
        resposta = self.client.post(f'/admin/denuncias/denuncia/{denuncia.pk}/change/', {
            'decisoes-TOTAL_FORMS': '1', 'decisoes-INITIAL_FORMS': '0',
            'decisoes-MIN_NUM_FORMS': '0', 'decisoes-MAX_NUM_FORMS': '1000',
            'decisoes-0-resultado': 'procedente', 'decisoes-0-acao': 'cancelar_carona',
            'decisoes-0-dias_suspensao': '', 'decisoes-0-justificativa': 'Comprovado.',
        })
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Só dá para cancelar carona se o alvo for uma carona.')
        self.assertFalse(denuncia.decisoes.exists())
