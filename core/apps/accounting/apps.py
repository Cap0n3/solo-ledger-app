from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AccountingConfig(AppConfig):
    name = "core.apps.accounting"
    label = "accounting"
    verbose_name = _("Comptabilité")
