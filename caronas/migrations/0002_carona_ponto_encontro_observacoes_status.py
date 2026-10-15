from django.db import migrations, models


def aberta_para_publicada(apps, schema_editor):
    Carona = apps.get_model('caronas', 'Carona')
    Carona.objects.filter(status='aberta').update(status='publicada')


def publicada_para_aberta(apps, schema_editor):
    Carona = apps.get_model('caronas', 'Carona')
    Carona.objects.filter(status__in=['publicada', 'lotada', 'em_andamento']).update(status='aberta')


class Migration(migrations.Migration):

    dependencies = [
        ('caronas', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='carona',
            name='ponto_encontro',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='carona',
            name='observacoes',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='carona',
            name='status',
            field=models.CharField(
                choices=[
                    ('publicada', 'Publicada'),
                    ('lotada', 'Lotada'),
                    ('em_andamento', 'Em andamento'),
                    ('concluida', 'Concluída'),
                    ('cancelada', 'Cancelada'),
                ],
                default='publicada',
                max_length=12,
            ),
        ),
        migrations.RunPython(aberta_para_publicada, publicada_para_aberta),
    ]
