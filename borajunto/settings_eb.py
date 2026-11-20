"""Configurações do deploy no AWS Elastic Beanstalk.

Usa tudo de settings.py e muda só o que o servidor precisa. O EB carrega
este arquivo pela variável DJANGO_SETTINGS_MODULE, definida em
.ebextensions/django.config.
"""

from .settings import *  # noqa: F401,F403
from .settings import BASE_DIR

# O EB acessa o app pelo domínio *.elasticbeanstalk.com e, na checagem de
# saúde, pelo IP interno da máquina. "*" aceita os dois.
ALLOWED_HOSTS = ['*']
CSRF_TRUSTED_ORIGINS = ['https://*.elasticbeanstalk.com']

# Pasta onde o collectstatic junta o CSS e as imagens de todos os apps.
# O nginx do EB serve /static/ direto dela (veja .ebextensions/django.config).
STATIC_ROOT = BASE_DIR / 'staticfiles'
