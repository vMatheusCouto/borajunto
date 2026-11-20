from io import BytesIO

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone
from PIL import Image, ImageOps

from .models import Perfil

TAMANHO_FOTO = 256
LIMITE_FOTO = 5 * 1024 * 1024


class EntrarForm(AuthenticationForm):
    username = forms.CharField(
        label='Matrícula',
        max_length=30,
        widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username'}),
    )
    password = forms.CharField(
        label='Senha',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'Matrícula ou senha incorretas.',
    }

    def get_invalid_login_error(self):
        mensagem = getattr(self.request, 'erro_suap', None)
        if mensagem:
            return forms.ValidationError(mensagem, code='erro_suap')
        return super().get_invalid_login_error()


def processar_foto(arquivo):
    imagem = ImageOps.exif_transpose(Image.open(arquivo))
    if imagem.mode != 'RGB':
        fundo = Image.new('RGB', imagem.size, 'white')
        fundo.paste(imagem, mask=imagem.convert('RGBA').getchannel('A'))
        imagem = fundo
    imagem = ImageOps.fit(imagem, (TAMANHO_FOTO, TAMANHO_FOTO))
    saida = BytesIO()
    imagem.save(saida, 'JPEG', quality=85)
    return saida.getvalue()


class EditarPerfilForm(forms.ModelForm):
    foto = forms.ImageField(
        label='Foto',
        required=False,
        widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
    )
    remover_foto = forms.BooleanField(label='Remover foto', required=False)

    class Meta:
        model = Perfil
        fields = ['apresentacao', 'receber_lembretes']
        widgets = {
            'apresentacao': forms.Textarea(attrs={
                'rows': 4,
                'maxlength': 280,
                'placeholder': 'Conte um pouco sobre você: curso, horários, se curte conversar na viagem…',
            }),
        }
        labels = {'receber_lembretes': 'Lembrete antes da carona'}

    def clean_foto(self):
        foto = self.cleaned_data.get('foto')
        if foto and foto.size > LIMITE_FOTO:
            raise forms.ValidationError('A foto pode ter no máximo 5 MB.')
        return foto

    def save(self, commit=True):
        perfil = super().save(commit=False)
        foto = self.cleaned_data.get('foto')
        if foto:
            perfil.foto = processar_foto(foto)
            perfil.foto_atualizada_em = timezone.now()
        elif self.cleaned_data.get('remover_foto'):
            perfil.foto = None
            perfil.foto_atualizada_em = None
        if commit:
            perfil.save()
        return perfil
