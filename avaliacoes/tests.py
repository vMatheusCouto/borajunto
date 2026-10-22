from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from caronas.models import Carona

from .models import Avaliacao


class AvaliacaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.motorista = User.objects.create_user('motorista')
        cls.ana = User.objects.create_user('ana')
        cls.lucas = User.objects.create_user('lucas')
        cls.caronas = [
            Carona.objects.create(
                motorista=cls.motorista, origem='Centro', destino='IFRN', ponto_encontro='Praça',
                data_hora=timezone.now() - timedelta(days=dias), vagas=3,
                status=Carona.Status.CONCLUIDA)
            for dias in (1, 2)
        ]

    def avaliar(self, avaliador, nota, carona=None, avaliado=None):
        return Avaliacao.objects.create(carona=carona or self.caronas[0], avaliador=avaliador,
                                        avaliado=avaliado or self.motorista, nota=nota)

    def test_reputacao_e_a_media_das_avaliacoes_validas(self):  # RF25, RN21
        self.avaliar(self.ana, 5)
        self.avaliar(self.lucas, 4)
        self.avaliar(self.ana, 3, carona=self.caronas[1])  # RN20: nova carona, nova nota
        removida = self.avaliar(self.lucas, 1, carona=self.caronas[1])
        removida.removida = True
        removida.save()
        self.assertEqual(Avaliacao.objects.reputacao(self.motorista),
                         {'media': 4.0, 'quantidade': 3})

    def test_sem_avaliacoes(self):
        self.assertEqual(Avaliacao.objects.reputacao(self.ana), {'media': None, 'quantidade': 0})

    def test_uma_nota_por_pessoa_em_cada_carona(self):  # RN20
        self.avaliar(self.ana, 5)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.avaliar(self.ana, 2)

    def test_nota_fora_de_1_a_5(self):
        for nota in (0, 6):
            with self.subTest(nota=nota), self.assertRaises(IntegrityError), transaction.atomic():
                self.avaliar(self.ana, nota)

    def test_ninguem_avalia_a_si_proprio(self):  # RN19
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.avaliar(self.ana, 5, avaliado=self.ana)
