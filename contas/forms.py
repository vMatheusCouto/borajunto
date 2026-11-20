from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone

from .models import conta_suspensa


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

    def confirm_login_allowed(self, user):
        if not conta_suspensa(user):
            return
        if user.is_active:
            fim = timezone.localtime(user.perfil.suspensa_ate)
            mensagem = f'Sua conta está suspensa até {fim:%d/%m/%Y às %H:%M}.'
        else:
            mensagem = 'Sua conta foi suspensa pela moderação.'
        raise forms.ValidationError(mensagem, code='inactive')
