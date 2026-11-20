from django.forms import forms
from denuncias.models import Denuncia


class DenunciaModelForm(forms.ModelForm):
    class Meta:
        model = Denuncia
        fields = ['motivo', 'descricao']
        labels = {'motivo':'Motivo', 'descricao':'Descrição'}
        widgets = {
              'motivo': forms.RadioSelect,
              'descricao': forms.Textarea(attrs={'rows': 4,'placeholder': 'Conte o que aconteceu, com data e local se puder.'}),
          }

    def clean_descricao(self):
        texto = self.cleaned_data['descricao'].strip()
        if not texto:
            raise forms.ValidationError('Descreva o problema')
        return texto

