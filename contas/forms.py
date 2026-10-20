from django import forms
from django.contrib.auth.forms import AuthenticationForm


class EntrarForm(AuthenticationForm):
    username = forms.CharField(
        label='Matrícula',
        max_length=30,
        widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username'}),
    )
    password = forms.CharField(
        label='Senha do SUAP',
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
