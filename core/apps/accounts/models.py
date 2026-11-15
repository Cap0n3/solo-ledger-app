import uuid
from datetime import date
from pathlib import Path

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from core.utils.months import month_range, month_span, validate_month_start

LESSON_YEAR_MAX_MONTHS = 12
PAYMENT_DUE_DAY_DEFAULT = 10
# Capped at 28 so the due day exists in every month, February included.
PAYMENT_DUE_DAY_MAX = 28


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
    payment_due_day = models.PositiveSmallIntegerField(
        _("jour limite de paiement"),
        default=PAYMENT_DUE_DAY_DEFAULT,
        validators=[MinValueValidator(1), MaxValueValidator(PAYMENT_DUE_DAY_MAX)],
        help_text=_("Un mois qui n'est pas entièrement payé ce jour-là est en retard."),
    )
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

    def payment_due_date(self, month: date) -> date:
        """Last day on which `month` can be fully paid without being late."""
        return month.replace(day=self.payment_due_day)


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


class LessonYear(ProfessionOwnedModel):
    """A lesson year (« année de cours ») of a profession: its billed months.

    Both bounds are first days of months, inclusive. August is typically not
    billed, so a year runs e.g. from September to July. Years of a profession
    never overlap; that rule needs the sibling years and lives in the services.
    """

    first_month = models.DateField(
        _("premier mois facturé"), validators=[validate_month_start]
    )
    last_month = models.DateField(
        _("dernier mois facturé"), validators=[validate_month_start]
    )

    class Meta:
        verbose_name = _("année de cours")
        verbose_name_plural = _("années de cours")
        ordering = ("-first_month",)
        constraints = (
            models.UniqueConstraint(
                fields=("profession", "first_month"),
                name="unique_lesson_year_start_per_profession",
                violation_error_message=_(
                    "Une année de cours commence déjà ce mois-là."
                ),
            ),
            models.CheckConstraint(
                condition=Q(last_month__gte=F("first_month")),
                name="lesson_year_last_month_after_first",
            ),
        )

    def __str__(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        """« 2026-2027 », or « 2026 » when the year stays within one calendar year."""
        if self.first_month.year == self.last_month.year:
            return str(self.first_month.year)
        return f"{self.first_month.year}-{self.last_month.year}"

    @property
    def months(self) -> list[date]:
        return month_range(self.first_month, self.last_month)

    def contains(self, month: date) -> bool:
        return self.first_month <= month <= self.last_month

    def clean(self) -> None:
        if self.first_month is None or self.last_month is None:
            return
        if self.last_month < self.first_month:
            raise ValidationError(
                {
                    "last_month": ValidationError(
                        _("Le dernier mois doit être postérieur ou égal au premier."),
                        code="last_before_first",
                    )
                }
            )
        if month_span(self.first_month, self.last_month) > LESSON_YEAR_MAX_MONTHS:
            raise ValidationError(
                {
                    "last_month": ValidationError(
                        _("Une année de cours couvre au plus douze mois."),
                        code="too_long",
                    )
                }
            )
