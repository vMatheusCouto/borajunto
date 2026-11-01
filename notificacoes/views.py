from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def lista(request):
    return render(request, 'notificacoes/lista.html', {
        'notificacoes': request.user.notificacoes.all(),
    })
