from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class StudentsConfig(AppConfig):
    name = "core.apps.students"
    label = "students"
    verbose_name = _("Élèves")
