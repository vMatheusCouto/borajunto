from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from caronas.models import Carona, Reserva

from . import alvos
from .forms import DenunciaForm
from .models import Denuncia


def destino(request):
    """Página de volta: o `next` da própria aplicação ou o perfil."""
    proxima = request.POST.get('next') or request.GET.get('next')
    if proxima and url_has_allowed_host_and_scheme(
            proxima, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return proxima
    return reverse('contas:perfil')


@login_required
def registrar(request, tipo, pk):
    """Registra a denúncia como pendente sobre um usuário, carona ou avaliação (RF26, UC09)."""
    campo, alvo, sobre = alvos.resolver(request, tipo, pk)
    voltar = destino(request)
    form = DenunciaForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        repetida = Denuncia.objects.filter(
            denunciante=request.user, status=Denuncia.Status.PENDENTE, **{campo: alvo}).exists()
        if repetida:
            messages.info(request, 'Você já denunciou isso. A coordenação está analisando.')
        else:
            denuncia = form.save(commit=False)
            denuncia.denunciante = request.user
            setattr(denuncia, campo, alvo)
            denuncia.save()
            messages.success(request, 'Denúncia enviada. A coordenação vai analisar a situação.')
        return redirect(voltar)

    return render(request, 'denuncias/registrar.html', {
        'form': form, 'sobre': sobre, 'voltar': voltar})


@login_required
def escolher(request):
    """Entrada pelo perfil: o estudante escolhe a carona ou a pessoa a denunciar (UC09)."""
    usuario = request.user
    caronas = list(
        Carona.objects
        .filter(Q(motorista=usuario) | Q(reservas__passageiro=usuario,
                                         reservas__status=Reserva.Status.ACEITA))
        .exclude(status=Carona.Status.CANCELADA)
        .select_related('motorista')
        .prefetch_related('reservas__passageiro')
        .distinct()
        .order_by('-data_hora')[:10]
    )
    for carona in caronas:
        passageiros = [r.passageiro for r in carona.reservas.all()
                       if r.status == Reserva.Status.ACEITA]
        carona.pessoas = [p for p in [carona.motorista, *passageiros] if p != usuario]
        carona.denunciavel = carona.motorista != usuario
    return render(request, 'denuncias/escolher.html', {'caronas': caronas})
