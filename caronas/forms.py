from datetime import datetime

from django import forms
from django.utils import timezone


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
    origem = forms.CharField(label='Origem', max_length=255)
    destino = forms.CharField(label='Destino', max_length=255)
    ponto_encontro = forms.CharField(label='Ponto de encontro', max_length=255)
    data = forms.DateField(label='Data', widget=forms.DateInput(attrs={'type': 'date'}))
    horario = forms.TimeField(label='Horário', widget=forms.TimeInput(attrs={'type': 'time'}))

    def clean(self):
        dados = super().clean()
        data = dados.get('data')
        horario = dados.get('horario')
        if data and horario:
            data_hora = timezone.make_aware(datetime.combine(data, horario))
            if data_hora < timezone.now():
                raise forms.ValidationError('A data e o horário precisam ser no futuro.')
        return dados


class VagasForm(forms.Form):
    vagas = forms.IntegerField(label='Vagas disponíveis', min_value=1, max_value=6, initial=3)
    observacoes = forms.CharField(label='Observações', max_length=500, required=False,
                                  widget=forms.Textarea(attrs={'rows': 3}))
