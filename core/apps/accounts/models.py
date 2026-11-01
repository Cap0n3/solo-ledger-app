import uuid
from pathlib import Path

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


def user_avatar_upload_to(instance: models.Model, filename: str) -> str:
    """Store each user's avatars in their own folder under an unguessable name.

    The original file name is dropped so it never leaks into a public URL.
    """
    extension = Path(filename).suffix.lower()
    return f"avatars/{instance.pk}/{uuid.uuid4().hex}{extension}"


class User(AbstractUser):
    """Application account. Each user owns one or more professions."""

    avatar = models.ImageField(_("avatar"), upload_to=user_avatar_upload_to, blank=True)

    class Meta:
        verbose_name = _("utilisateur")
        verbose_name_plural = _("utilisateurs")

    @property
    def display_name(self) -> str:
        """Name shown in the interface: the first name, or the username without one."""
        return self.first_name or self.username

    @property
    def initial(self) -> str:
        """Letter shown in place of the avatar when none is set."""
        return self.display_name[:1].upper()


class Profession(models.Model):
    """An independent activity (e.g. guitar lessons) owned by one user.

    Shown as « activité » in the UI. Every business record belongs to exactly
    one profession: this is how data is kept separate between users.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="professions",
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
                name="unique_profession_name_per_user",
                violation_error_message=_("Une activité porte déjà ce nom."),
            ),
        )

    def __str__(self) -> str:
        return self.name


class ProfessionOwnedModel(models.Model):
    """Base class for every business record: ties it to one profession.

    Selectors and services must always filter through `profession`; views must
    never fetch such a record by id alone.
    """

    profession = models.ForeignKey(
        Profession,
        on_delete=models.PROTECT,
        related_name="%(class)s_set",
        verbose_name=_("activité"),
    )

    class Meta:
        abstract = True
