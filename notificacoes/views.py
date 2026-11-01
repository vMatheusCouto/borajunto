from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def lista(request):
    """Central de notificações (UC07): mostra as não lidas destacadas e as marca como lidas."""
    notificacoes = request.user.notificacoes.select_related('carona')
    resposta = render(request, 'notificacoes/lista.html', {'notificacoes': list(notificacoes)})
    notificacoes.filter(lida=False).update(lida=True)
    return resposta
