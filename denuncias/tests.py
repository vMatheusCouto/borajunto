from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import DecisaoModeracao, Denuncia


class DenunciaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.ana = User.objects.create_user('ana')
        cls.lucas = User.objects.create_user('lucas')
        cls.admin = User.objects.create_superuser('marina')

    def denunciar(self, **alvo):
        return Denuncia.objects.create(denunciante=self.ana, motivo=Denuncia.Motivo.CONDUTA,
                                       descricao='Foi grosseiro.', **alvo)

    def test_denuncia_comeca_pendente(self):
        denuncia = self.denunciar(usuario=self.lucas)
        self.assertEqual(denuncia.status, Denuncia.Status.PENDENTE)
        self.assertEqual(denuncia.alvo, self.lucas)

    def test_denuncia_exige_um_alvo(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.denunciar()

    def test_decisao_exige_justificativa(self):  # RN22
        denuncia = self.denunciar(usuario=self.lucas)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DecisaoModeracao.objects.create(denuncia=denuncia, administrador=self.admin,
                                            resultado=Denuncia.Status.IMPROCEDENTE)
