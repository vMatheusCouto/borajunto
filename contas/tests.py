from datetime import timedelta
from unittest.mock import patch

import suapy
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from avaliacoes.models import Avaliacao
from caronas.models import Carona, Reserva
from notificacoes.models import Notificacao

from .backends import ERRO_SUAP, ERRO_VINCULO
from .models import Perfil

AUTENTICAR = 'contas.backends.suapy.autenticar'


def perfil_suap(ativo=True, nome='Ana Souza', curso='Informática'):
    vinculo = suapy.Vinculo(identificador='20231014040001', tipo='Aluno', campus='PF',
                            ativo=ativo, curso=curso)
    return suapy.Perfil(matricula='20231014040001', nome=nome,
                        email='ana.souza@escolar.ifrn.edu.br', campus='PF',
                        tipo_usuario='Aluno', foto='/media/ana.jpg', vinculos=(vinculo,))


class LoginSuapTests(TestCase):
    def entrar(self, senha='senha'):
        return self.client.post(reverse('contas:entrar'),
                                {'username': '20231014040001', 'password': senha})

    @patch(AUTENTICAR, return_value=perfil_suap())
    def test_aluno_ativo_entra_e_perfil_e_criado(self, autenticar):
        resposta = self.entrar()
        self.assertRedirects(resposta, reverse('contas:inicio'))
        autenticar.assert_called_once()
        user = get_user_model().objects.get(username='20231014040001')
        self.assertEqual((user.first_name, user.last_name), ('Ana', 'Souza'))
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.perfil.curso, 'Informática')
        inicio = self.client.get(reverse('contas:inicio'))
        self.assertContains(inicio, '<h1>Ana</h1>', html=True)
        self.assertContains(inicio, 'Informática · campus PF')
        self.assertContains(inicio, 'Matrícula 20231014040001')
        self.assertContains(inicio, reverse('contas:sair'))

    @patch(AUTENTICAR)
    def test_novo_login_atualiza_dados_do_suap(self, autenticar):
        autenticar.return_value = perfil_suap()
        self.entrar()
        self.client.logout()
        autenticar.return_value = perfil_suap(nome='Ana Maria', curso='Redes')
        self.entrar()
        self.assertEqual(Perfil.objects.count(), 1)
        perfil = Perfil.objects.get()
        self.assertEqual((perfil.usuario.first_name, perfil.curso), ('Ana', 'Redes'))
        self.assertEqual(perfil.usuario.last_name, 'Maria')

    @patch(AUTENTICAR, side_effect=suapy.SuapAuthError('negado'))
    def test_senha_errada(self, _):
        resposta = self.entrar('errada')
        self.assertContains(resposta, 'Matrícula ou senha incorretas.')
        self.assertFalse(get_user_model().objects.exists())

    @patch(AUTENTICAR, return_value=perfil_suap(ativo=False))
    def test_vinculo_inativo_e_negado(self, _):  # RN01
        resposta = self.entrar()
        self.assertContains(resposta, ERRO_VINCULO)
        self.assertFalse(get_user_model().objects.exists())

    @patch(AUTENTICAR, side_effect=suapy.SuapError('timeout'))
    def test_suap_indisponivel(self, _):
        with self.assertLogs('contas.backends', 'WARNING'):
            resposta = self.entrar()
        self.assertContains(resposta, ERRO_SUAP)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_inicio_exige_login(self):
        resposta = self.client.get(reverse('contas:inicio'))
        self.assertRedirects(resposta, reverse('contas:entrar') + '?next=/')

    @patch(AUTENTICAR, return_value=perfil_suap())
    def test_sair_encerra_sessao(self, _):  # RF03
        self.entrar()
        resposta = self.client.post(reverse('contas:sair'))
        self.assertRedirects(resposta, reverse('contas:entrar'))
        self.assertNotIn('_auth_user_id', self.client.session)


class InicioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.ana = User.objects.create_user('ana', first_name='Ana', last_name='Souza')
        lucas = User.objects.create_user('lucas', first_name='Lucas', last_name='Almeida')
        outro = User.objects.create_user('outro')
        cls.amanha = timezone.localtime() + timedelta(days=1)

        def carona(**campos):
            dados = {'motorista': lucas, 'origem': 'Pau dos Ferros', 'destino': 'Campus Mossoró',
                     'ponto_encontro': 'Praça da Matriz', 'data_hora': cls.amanha, 'vagas': 3,
                     **campos}
            return Carona.objects.create(**dados)

        disponivel = carona()
        carona(origem='Caicó', data_hora=cls.amanha + timedelta(hours=1))
        carona(origem='Própria', motorista=cls.ana)  # RN09
        carona(origem='Passada', data_hora=cls.amanha - timedelta(days=3))
        carona(origem='Cancelada', status=Carona.Status.CANCELADA)
        lotada = carona(origem='Lotada', vagas=1)
        Reserva.objects.create(carona=lotada, passageiro=outro, status=Reserva.Status.ACEITA)
        Reserva.objects.create(carona=disponivel, passageiro=outro, status=Reserva.Status.ACEITA)
        concluida = carona(status=Carona.Status.CONCLUIDA,
                           data_hora=cls.amanha - timedelta(days=5))
        Avaliacao.objects.create(carona=concluida, avaliador=outro, avaliado=lucas, nota=5)
        Avaliacao.objects.create(carona=concluida, avaliador=cls.ana, avaliado=lucas, nota=4)

    def setUp(self):
        self.client.force_login(self.ana)

    def origens(self, resposta):
        return [c.origem for c in resposta.context['caronas']]

    def test_lista_apenas_caronas_disponiveis(self):  # RN07, RN09
        resposta = self.client.get(reverse('contas:inicio'))
        self.assertEqual(self.origens(resposta), ['Pau dos Ferros', 'Caicó'])
        self.assertContains(resposta, '2 caronas encontradas')

    def test_card_mostra_vagas_restantes_e_reputacao(self):  # RF14, RF17, RF25
        resposta = self.client.get(reverse('contas:inicio'), {'origem': 'pau'})
        self.assertEqual(self.origens(resposta), ['Pau dos Ferros'])
        self.assertContains(resposta, '2 vagas')
        self.assertContains(resposta, '★ 4,5')
        self.assertContains(resposta, 'Lucas Almeida')

    def test_busca_por_data(self):  # RF13
        resposta = self.client.get(reverse('contas:inicio'), {'data': self.amanha.date().isoformat()})
        self.assertEqual(len(self.origens(resposta)), 2)
        resposta = self.client.get(reverse('contas:inicio'), {'data': '2000-01-01'})
        self.assertContains(resposta, 'Nenhuma carona encontrada')

    def test_parametro_invalido_mostra_erro(self):  # UC04 E1
        resposta = self.client.get(reverse('contas:inicio'), {'data': 'ontem'})
        self.assertContains(resposta, 'role="alert"')
        self.assertEqual(len(self.origens(resposta)), 2)

    def test_indica_notificacoes_nao_lidas(self):
        self.assertNotContains(self.client.get(reverse('contas:inicio')), 'class="ponto"')
        Notificacao.objects.create(destinatario=self.ana, tipo=Notificacao.Tipo.DECISAO,
                                   mensagem='Sua vaga foi aceita.')
        self.assertContains(self.client.get(reverse('contas:inicio')), 'class="ponto"')

