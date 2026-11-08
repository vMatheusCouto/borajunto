from pathlib import Path

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

PASTA = Path(__file__).resolve().parent.parent / 'static' / 'contas' / 'icones'


@register.simple_tag
def icone(nome, tamanho=18):
    svg = (PASTA / f'{nome}.svg').read_text()
    atributos = f'class="ic" width="{tamanho}" height="{tamanho}" aria-hidden="true"'
    return mark_safe(svg.replace('<svg', f'<svg {atributos}', 1))
