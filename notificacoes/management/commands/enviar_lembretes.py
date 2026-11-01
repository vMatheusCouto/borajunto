from django.core.management.base import BaseCommand

from notificacoes.lembretes import enviar_lembretes


class Command(BaseCommand):
    help = 'Gera os lembretes das caronas que saem nos próximos 60 minutos (RF22).'

    def handle(self, *args, **options):
        criados = enviar_lembretes()
        self.stdout.write(f'{criados} lembrete(s) gerado(s).')
