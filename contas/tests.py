from unittest.mock import patch

import suapy
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

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
        self.assertContains(self.client.get(reverse('contas:inicio')), 'Olá, Ana')

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
