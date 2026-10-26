from datetime import datetime

from django import forms
from django.utils import timezone

VAGAS_MAXIMAS = 6


class BuscaForm(forms.Form):
    """Filtros da busca de caronas por origem, destino e data (RF13)."""

    origem = forms.CharField(label='Origem', max_length=255, required=False)
    destino = forms.CharField(label='Destino', max_length=255, required=False)
    data = forms.DateField(label='Data', required=False,
                           widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    hora = forms.TimeField(label='A partir de', required=False,
                           widget=forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'))

    def filtrar(self, caronas):
        dados = self.cleaned_data
        if dados['origem']:
            caronas = caronas.filter(origem__icontains=dados['origem'])
        if dados['destino']:
            caronas = caronas.filter(destino__icontains=dados['destino'])
        if dados['data']:
            caronas = caronas.filter(data_hora__date=dados['data'])
        if dados['hora']:
            caronas = caronas.filter(data_hora__time__gte=dados['hora'])
        return caronas


class TrajetoForm(forms.Form):
    origem = forms.CharField(label='Origem', max_length=255,
                             widget=forms.TextInput(attrs={'placeholder': 'Ex.: Pau dos Ferros'}))
    destino = forms.CharField(label='Destino', max_length=255,
                              widget=forms.TextInput(attrs={'placeholder': 'Ex.: IFRN — Campus Mossoró'}))
    ponto_encontro = forms.CharField(
        label='Ponto de encontro', max_length=255,
        widget=forms.TextInput(attrs={'placeholder': 'Ex.: praça central'}))
    data = forms.DateField(label='Data', widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    horario = forms.TimeField(label='Horário', widget=forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'))

    def clean(self):
        dados = super().clean()
        if dados.get('data') and dados.get('horario'):
            data_hora = timezone.make_aware(datetime.combine(dados['data'], dados['horario']))
            if data_hora <= timezone.now():
                raise forms.ValidationError('Escolha uma data e um horário que ainda não passaram.')
            dados['data_hora'] = data_hora
        return dados

    def para_sessao(self):
        dados = self.cleaned_data
        return {'origem': dados['origem'], 'destino': dados['destino'],
                'ponto_encontro': dados['ponto_encontro'],
                'data': dados['data'].isoformat(), 'horario': dados['horario'].strftime('%H:%M')}


class VagasForm(forms.Form):
    vagas = forms.IntegerField(label='Vagas disponíveis', min_value=1, max_value=VAGAS_MAXIMAS, initial=3)
    observacoes = forms.CharField(
        label='Observações', max_length=500, required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Ex.: Saio da praça central. Sem bagagem grande, por favor.'}))
