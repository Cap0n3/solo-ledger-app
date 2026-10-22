from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BankImportsConfig(AppConfig):
    name = "core.apps.bank_imports"
    label = "bank_imports"
    verbose_name = _("Import bancaire")
