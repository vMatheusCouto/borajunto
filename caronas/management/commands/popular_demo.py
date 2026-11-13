from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from avaliacoes.models import Avaliacao
from caronas.models import Carona, Reserva
from contas.models import Perfil

PESSOAS = [
    ('demo.ana', 'Ana', 'Souza', 'Tecnologia em Análise e Desenvolvimento de Sistemas', 'CNAT'),
    ('demo.bruno', 'Bruno', 'Lima', 'Engenharia de Energias', 'CNAT'),
    ('demo.carla', 'Carla', 'Mendes', 'Técnico em Informática', 'ZN'),
    ('demo.diego', 'Diego', 'Rocha', 'Licenciatura em Física', 'CNAT'),
    ('demo.elisa', 'Elisa', 'Freitas', 'Técnico em Edificações', 'PAR'),
    ('demo.felipe', 'Felipe', 'Costa', 'Gestão Pública', 'CAL'),
]

# (motorista, origem, destino, ponto de encontro, dias à frente, hora, vagas, passageiros confirmados)
CARONAS_FUTURAS = [
    ('demo.ana', 'Ponta Negra', 'IFRN Campus Natal-Central', 'Posto da Av. Roberto Freire', 1, 6, 3, ['demo.carla']),
    ('demo.bruno', 'Parnamirim', 'IFRN Campus Natal-Central', 'Rodoviária de Parnamirim', 1, 6, 4, []),
    ('demo.diego', 'IFRN Campus Natal-Central', 'Zona Norte', 'Portão principal do campus', 1, 17, 2, ['demo.elisa']),
    ('demo.carla', 'Zona Norte', 'IFRN Campus Natal-Zona Norte', 'Shopping Via Direta', 2, 12, 3, []),
    ('demo.elisa', 'Parnamirim', 'IFRN Campus Parnamirim', 'Praça do Nova Parnamirim', 2, 7, 2, []),
    ('demo.felipe', 'Natal', 'IFRN Campus Natal-Cidade Alta', 'Midway Mall', 3, 13, 3, ['demo.ana']),
]

# (motorista, origem, destino, dias atrás, passageiros, notas recebidas pelo motorista)
CARONAS_CONCLUIDAS = [
    ('demo.ana', 'Ponta Negra', 'IFRN Campus Natal-Central', 3, ['demo.bruno', 'demo.diego'], [5, 5]),
    ('demo.bruno', 'Parnamirim', 'IFRN Campus Natal-Central', 5, ['demo.carla'], [4]),
    ('demo.diego', 'IFRN Campus Natal-Central', 'Zona Norte', 4, ['demo.felipe', 'demo.ana'], [5, 4]),
]


class Command(BaseCommand):
    help = 'Cria estudantes, caronas, reservas e avaliações fictícios para demonstração.'

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(username__startswith='demo.').exists():
            self.stdout.write('Dados de demonstração já existem.')
            return

        usuarios = {}
        for i, (username, nome, sobrenome, curso, campus) in enumerate(PESSOAS, start=1):
            user = User(username=username, first_name=nome, last_name=sobrenome,
                        email=f'{username}@exemplo.com')
            user.set_unusable_password()
            user.save()
            Perfil.objects.create(usuario=user, matricula=f'DEMO{i:04d}', curso=curso, campus=campus)
            usuarios[username] = user

        hoje = timezone.localtime().replace(minute=0, second=0, microsecond=0)

        for motorista, origem, destino, encontro, dias, hora, vagas, passageiros in CARONAS_FUTURAS:
            carona = Carona.objects.create(
                motorista=usuarios[motorista], origem=origem, destino=destino,
                ponto_encontro=encontro, vagas=vagas,
                data_hora=(hoje + timedelta(days=dias)).replace(hour=hora),
            )
            for passageiro in passageiros:
                Reserva.objects.create(carona=carona, passageiro=usuarios[passageiro],
                                       status=Reserva.Status.ACEITA)
            carona.atualizar_lotacao()

        for motorista, origem, destino, dias, passageiros, notas in CARONAS_CONCLUIDAS:
            carona = Carona.objects.create(
                motorista=usuarios[motorista], origem=origem, destino=destino,
                ponto_encontro='Entrada principal', vagas=len(passageiros) + 1,
                data_hora=(hoje - timedelta(days=dias)).replace(hour=7),
                status=Carona.Status.CONCLUIDA,
            )
            for passageiro, nota in zip(passageiros, notas):
                Reserva.objects.create(carona=carona, passageiro=usuarios[passageiro],
                                       status=Reserva.Status.ACEITA)
                Avaliacao.objects.create(carona=carona, avaliador=usuarios[passageiro],
                                         avaliado=usuarios[motorista], nota=nota)
                Avaliacao.objects.create(carona=carona, avaliador=usuarios[motorista],
                                         avaliado=usuarios[passageiro], nota=5)

        self.stdout.write(self.style.SUCCESS(
            f'{len(usuarios)} estudantes e {Carona.objects.count()} caronas de demonstração criados.'))
