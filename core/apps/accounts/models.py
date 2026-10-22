from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """Application account. Each user owns one or more activities."""

    class Meta:
        verbose_name = _("utilisateur")
        verbose_name_plural = _("utilisateurs")


class Activity(models.Model):
    """An independent teaching activity (e.g. guitar lessons) owned by one user.

    Every business record belongs to exactly one activity: this is how data is
    kept separate between users.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="activities",
        verbose_name=_("utilisateur"),
    )
    name = models.CharField(_("nom"), max_length=100)
    created_at = models.DateTimeField(_("créée le"), auto_now_add=True)

    class Meta:
        verbose_name = _("activité")
        verbose_name_plural = _("activités")
        ordering = ("name",)
        constraints = (
            models.UniqueConstraint(
                fields=("user", "name"),
                name="unique_activity_name_per_user",
                violation_error_message=_("Une activité porte déjà ce nom."),
            ),
        )

    def __str__(self) -> str:
        return self.name


class ActivityOwnedModel(models.Model):
    """Base class for every business record: ties it to one activity.

    Selectors and services must always filter through `activity`; views must
    never fetch such a record by id alone.
    """

    activity = models.ForeignKey(
        Activity,
        on_delete=models.PROTECT,
        related_name="%(class)s_set",
        verbose_name=_("activité"),
    )

    class Meta:
        abstract = True
