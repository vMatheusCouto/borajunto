from django import forms


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
