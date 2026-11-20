from django import forms

from .models import Denuncia

# Motivos oferecidos na tela, na ordem do protótipo.
MOTIVOS = [
    Denuncia.Motivo.AUSENCIA,
    Denuncia.Motivo.CONDUTA,
    Denuncia.Motivo.COBRANCA,
    Denuncia.Motivo.PERFIL_FALSO,
    Denuncia.Motivo.OUTRO,
]


class DenunciaForm(forms.ModelForm):
    """Motivo e descrição da denúncia; o alvo vem da URL (UC09)."""

    motivo = forms.ChoiceField(
        label='Tipo do problema',
        choices=[(m.value, m.label) for m in MOTIVOS],
        widget=forms.RadioSelect,
        error_messages={'required': 'Escolha o tipo do problema.'},
    )

    class Meta:
        model = Denuncia
        fields = ['motivo', 'descricao']
        labels = {'descricao': 'Detalhes'}
        widgets = {
            'descricao': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Conte o que aconteceu, com data e local se puder.',
            }),
        }
        error_messages = {
            'descricao': {'required': 'Descreva o problema.'},
        }

    def clean_descricao(self):
        texto = self.cleaned_data['descricao'].strip()
        if not texto:
            raise forms.ValidationError('Descreva o problema.')
        return texto
