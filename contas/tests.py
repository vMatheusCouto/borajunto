from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from avaliacoes.models import Avaliacao
from caronas.models import Carona

from .models import Perfil


class IconeTests(TestCase):
    def renderizar(self, trecho):
        from django.template import Context, Template
        return Template('{% load icones %}' + trecho).render(Context())

    def test_renderiza_svg_inline_decorativo(self):
        html = self.renderizar("{% icone 'busca' %}")
        self.assertIn('<svg class="ic" width="18" height="18" aria-hidden="true"', html)
        self.assertIn('stroke="currentColor"', html)
        self.assertIn('<circle cx="11" cy="11" r="8"/>', html)

    def test_aceita_tamanho(self):
        self.assertIn('width="22" height="22"', self.renderizar("{% icone 'mais' 22 %}"))

    def test_todos_os_icones_usados_existem(self):
        import re
        from pathlib import Path
        raiz = Path(__file__).resolve().parent.parent
        usados = {nome for arquivo in raiz.glob('*/templates/**/*.html')
                  for nome in re.findall(r"\{% icone '([\w-]+)'", arquivo.read_text())}
        self.assertTrue(usados)
        for nome in usados:
            self.renderizar("{% icone '" + nome + "' %}")


class PerfilPublicoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.ana = User.objects.create_user('ana', first_name='Ana', last_name='Souza')
        cls.lucas = User.objects.create_user('lucas', first_name='Lucas', last_name='Almeida',
                                             email='lucas@escolar.ifrn.edu.br')
        Perfil.objects.create(usuario=cls.lucas, matricula='20231014040002',
                              curso='Informática', campus='PF')
        outro = User.objects.create_user('outro')
        amanha = timezone.localtime() + timedelta(days=1)

        def carona(**campos):
            dados = {'motorista': cls.lucas, 'origem': 'Pau dos Ferros', 'destino': 'Campus Mossoró',
                     'ponto_encontro': 'Praça da Matriz', 'data_hora': amanha, 'vagas': 3,
                     **campos}
            return Carona.objects.create(**dados)

        carona(origem='Próxima')
        carona(origem='Cancelada', status=Carona.Status.CANCELADA)
        concluida = carona(origem='Antiga', status=Carona.Status.CONCLUIDA,
                           data_hora=amanha - timedelta(days=5))
        Avaliacao.objects.create(carona=concluida, avaliador=cls.ana, avaliado=cls.lucas, nota=4)
        Avaliacao.objects.create(carona=concluida, avaliador=outro, avaliado=cls.lucas, nota=1,
                                 removida=True)  # RN21

    def setUp(self):
        self.client.force_login(self.ana)

    def url(self, usuario):
        return reverse('contas:perfil_publico', args=[usuario.pk])

    def test_exige_login(self):
        self.client.logout()
        resposta = self.client.get(self.url(self.lucas))
        self.assertRedirects(resposta, reverse('contas:entrar') + '?next=' + self.url(self.lucas))

    def test_mostra_dados_reputacao_e_proximas_caronas(self):  # RF25
        resposta = self.client.get(self.url(self.lucas))
        self.assertContains(resposta, '<h1>Lucas Almeida</h1>', html=True)
        self.assertContains(resposta, 'Informática · Campus PF')
        self.assertEqual(resposta.context['caronas'], 1)
        self.assertEqual(resposta.context['como_motorista'], 1)
        self.assertEqual(resposta.context['como_passageiro'], 0)
        self.assertEqual(resposta.context['ultima_carona'].origem, 'Antiga')
        self.assertEqual(resposta.context['avaliacoes_feitas'], 0)
        self.assertEqual(resposta.context['reputacao'], {'media': 4, 'quantidade': 1})
        origens = [c.origem for c in resposta.context['proximas']]
        self.assertEqual(origens, ['Próxima'])
        self.assertContains(resposta, 'Denunciar usuário')

    def test_nao_mostra_email_nem_matricula(self):
        resposta = self.client.get(self.url(self.lucas))
        self.assertNotContains(resposta, 'lucas@escolar.ifrn.edu.br')
        self.assertNotContains(resposta, '20231014040002')

    def test_sem_avaliacoes(self):  # RN21
        resposta = self.client.get(self.url(get_user_model().objects.get(username='outro')))
        self.assertContains(resposta, 'sem avaliações')
        self.assertContains(resposta, 'nenhuma ainda')
        self.assertNotContains(resposta, 'Próximas caronas')  # sem caronas, a seção some

    def test_o_proprio_perfil_redireciona(self):
        resposta = self.client.get(self.url(self.ana))
        self.assertRedirects(resposta, reverse('contas:perfil'))

    def test_usuario_inexistente_ou_inativo(self):
        self.assertEqual(self.client.get(reverse('contas:perfil_publico', args=[9999])).status_code, 404)
        self.lucas.is_active = False
        self.lucas.save()
        self.assertEqual(self.client.get(self.url(self.lucas)).status_code, 404)
