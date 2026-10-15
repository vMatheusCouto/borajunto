from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .forms import EntrarForm


class EntrarView(auth_views.LoginView):
    form_class = EntrarForm
    template_name = 'contas/entrar.html'
    redirect_authenticated_user = True


@login_required
def inicio(request):
    return render(request, 'contas/inicio.html')
