from django.test import TestCase

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
