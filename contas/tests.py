from datetime import timedelta
from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from PIL import Image

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


class EditarPerfilTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.ana = User.objects.create_user('ana', first_name='Ana', last_name='Souza')
        cls.lucas = User.objects.create_user('lucas', first_name='Lucas', last_name='Almeida')
        Perfil.objects.create(usuario=cls.ana, matricula='ana', foto_url='https://suap/ana.jpg')
        Perfil.objects.create(usuario=cls.lucas, matricula='lucas')

    def setUp(self):
        self.client.force_login(self.ana)

    def imagem(self, formato='PNG', tamanho=(600, 400), modo='RGBA'):
        arquivo = BytesIO()
        Image.new(modo, tamanho, (200, 30, 30, 255) if modo == 'RGBA' else (200, 30, 30)).save(arquivo, formato)
        return SimpleUploadedFile(f'foto.{formato.lower()}', arquivo.getvalue(), f'image/{formato.lower()}')

    def salvar(self, **dados):
        dados = {'apresentacao': '', 'receber_lembretes': 'on', **dados}
        return self.client.post('/perfil/editar/', dados)

    def test_tela_abre(self):
        resposta = self.client.get('/perfil/editar/')
        self.assertContains(resposta, 'Editar perfil')
        self.assertContains(resposta, 'enctype="multipart/form-data"')

    def test_salva_apresentacao_e_lembretes(self):
        resposta = self.salvar(apresentacao='Curto conversar na viagem.', receber_lembretes='')
        self.assertRedirects(resposta, '/perfil/')
        self.ana.perfil.refresh_from_db()
        self.assertEqual(self.ana.perfil.apresentacao, 'Curto conversar na viagem.')
        self.assertFalse(self.ana.perfil.receber_lembretes)
        self.assertContains(self.client.get('/perfil/'), 'Curto conversar na viagem.')

    def test_apresentacao_tem_limite(self):
        resposta = self.salvar(apresentacao='a' * 281)
        self.assertEqual(resposta.status_code, 200)
        self.ana.perfil.refresh_from_db()
        self.assertEqual(self.ana.perfil.apresentacao, '')

    def test_envia_foto_redimensionada(self):
        self.salvar(foto=self.imagem())
        self.ana.perfil.refresh_from_db()
        url = self.ana.perfil.foto_enviada_url
        self.assertTrue(url.startswith(f'/perfil/foto/{self.ana.pk}/?v='))
        resposta = self.client.get(url)
        self.assertEqual(resposta['Content-Type'], 'image/jpeg')
        self.assertIn('max-age', resposta['Cache-Control'])
        imagem = Image.open(BytesIO(resposta.content))
        self.assertEqual(imagem.size, (256, 256))
        self.assertEqual(imagem.format, 'JPEG')
        self.assertContains(self.client.get('/perfil/'), url)

    def test_remove_foto_e_volta_para_a_do_suap(self):
        self.salvar(foto=self.imagem())
        self.salvar(remover_foto='on')
        self.ana.perfil.refresh_from_db()
        self.assertIsNone(self.ana.perfil.foto)
        self.assertEqual(self.ana.perfil.foto_exibida_url, 'https://suap/ana.jpg')
        self.assertEqual(self.client.get(f'/perfil/foto/{self.ana.pk}/').status_code, 404)

    def test_recusa_arquivo_que_nao_e_imagem(self):
        resposta = self.salvar(foto=SimpleUploadedFile('foto.png', b'nada disso', 'image/png'))
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context['form'].errors['foto'])

    def test_recusa_foto_grande(self):
        with mock.patch('contas.forms.LIMITE_FOTO', 10):
            resposta = self.salvar(foto=self.imagem('JPEG', modo='RGB'))
        self.assertContains(resposta, 'A foto pode ter no máximo 5 MB.')

    def test_avatar_mostra_so_a_foto_enviada(self):
        carona = Carona.objects.create(motorista=self.ana, origem='Natal', destino='Parnamirim',
                                       ponto_encontro='Portão', vagas=2,
                                       data_hora=timezone.now() + timedelta(days=1))
        self.client.force_login(self.lucas)
        detalhe = self.client.get(f'/caronas/{carona.pk}/')
        self.assertNotContains(detalhe, 'https://suap/ana.jpg')
        self.assertContains(detalhe, '>AS</span>')

        self.client.force_login(self.ana)
        self.salvar(foto=self.imagem(), apresentacao='Saio sempre pontualmente.')
        self.ana.perfil.refresh_from_db()
        self.client.force_login(self.lucas)
        for url in (f'/caronas/{carona.pk}/', '/'):
            self.assertContains(self.client.get(url), self.ana.perfil.foto_enviada_url)
        self.assertContains(self.client.get(f'/caronas/{carona.pk}/'), 'Saio sempre pontualmente.')

    def test_foto_exige_login(self):
        self.salvar(foto=self.imagem())
        self.client.logout()
        resposta = self.client.get(f'/perfil/foto/{self.ana.pk}/')
        self.assertEqual(resposta.status_code, 302)
