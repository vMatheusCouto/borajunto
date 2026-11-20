from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from caronas.models import Carona, Reserva
from contas.models import Perfil

from .lembretes import enviar_lembretes
from .models import Notificacao


class LembreteTests(TestCase):
    def test_respeita_quem_desligou_os_lembretes(self):
        User = get_user_model()
        lucas = User.objects.create_user('lucas')
        ana = User.objects.create_user('ana')
        bruno = User.objects.create_user('bruno')
        Perfil.objects.create(usuario=lucas, matricula='lucas')
        Perfil.objects.create(usuario=ana, matricula='ana', receber_lembretes=False)
        carona = Carona.objects.create(motorista=lucas, origem='Natal', destino='Parnamirim',
                                       ponto_encontro='Portão', vagas=2,
                                       data_hora=timezone.now() + timedelta(minutes=30))
        for passageiro in (ana, bruno):
            Reserva.objects.create(carona=carona, passageiro=passageiro, status=Reserva.Status.ACEITA)

        self.assertEqual(enviar_lembretes(), 2)
        avisados = set(Notificacao.objects.filter(tipo=Notificacao.Tipo.LEMBRETE)
                       .values_list('destinatario__username', flat=True))
        self.assertEqual(avisados, {'lucas', 'bruno'})
