from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from core.apps.accounts.models import ProfessionOwnedModel
from core.utils.months import month_add, validate_month_start


class Plan(ProfessionOwnedModel):
    """A course plan (« formule ») of a profession with a stable price.

    Monthly plans drive the automatic expected payments; single-lesson plans
    (« à la carte ») are billed per lesson and entered by hand. Old plans still
    used by some students are archived rather than deleted.
    """

    class Kind(models.TextChoices):
        MONTHLY = "monthly", _("Mensuelle")
        SINGLE_LESSON = "single_lesson", _("À la carte")

    name = models.CharField(_("nom"), max_length=100)
    description = models.TextField(_("description"), blank=True)
    price = models.DecimalField(
        _("prix"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    kind = models.CharField(
        _("type"), max_length=20, choices=Kind, default=Kind.MONTHLY
    )
    is_archived = models.BooleanField(_("archivée"), default=False)
    created_at = models.DateTimeField(_("créée le"), auto_now_add=True)

    class Meta:
        verbose_name = _("formule")
        verbose_name_plural = _("formules")
        ordering = ("is_archived", "name")
        constraints = (
            models.UniqueConstraint(
                fields=("profession", "name"),
                name="unique_plan_name_per_profession",
                violation_error_message=_("Une formule porte déjà ce nom."),
            ),
        )

    def __str__(self) -> str:
        return self.name

    @property
    def is_monthly(self) -> bool:
        return self.kind == self.Kind.MONTHLY


class Payer(ProfessionOwnedModel):
    """Someone who pays for one or more students, typically a parent.

    Carries the payment reference name used to recognise bank transfers for
    every student attached to it, whether or not a family plan is assigned.
    """

    name = models.CharField(_("nom"), max_length=150)
    payment_reference_name = models.CharField(
        _("nom de référence pour les paiements"),
        max_length=150,
        blank=True,
        help_text=_(
            "Nom tel qu'il apparaît sur les virements. Vide : le nom du payeur."
        ),
    )
    email = models.EmailField(_("e-mail"), blank=True)
    phone = models.CharField(_("téléphone"), max_length=50, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(_("créé le"), auto_now_add=True)

    class Meta:
        verbose_name = _("payeur")
        verbose_name_plural = _("payeurs")
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    @property
    def reference_name(self) -> str:
        return self.payment_reference_name or self.name


class Student(ProfessionOwnedModel):
    """A student (« élève ») of a profession.

    `end_date` is the billing boundary that counts: expected payments stop at
    its month. `status` is informational and only stores `active` or `ended`:
    « en pause » is derived from an ongoing `StudentPause`, never saved.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", _("Actif")
        PAUSED = "paused", _("En pause")
        ENDED = "ended", _("Terminé")

    first_name = models.CharField(_("prénom"), max_length=100)
    last_name = models.CharField(_("nom"), max_length=100)
    email = models.EmailField(_("e-mail"), blank=True)
    phone = models.CharField(_("téléphone"), max_length=50, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    start_date = models.DateField(_("date de début des cours"))
    end_date = models.DateField(_("date de fin des cours"), null=True, blank=True)
    status = models.CharField(
        _("statut"), max_length=10, choices=Status, default=Status.ACTIVE
    )
    payment_reference_name = models.CharField(
        _("nom de référence pour les paiements"),
        max_length=150,
        blank=True,
        help_text=_(
            "Nom tel qu'il apparaît sur les virements. Vide : le nom de l'élève. "
            "Ignoré si un payeur est renseigné."
        ),
    )
    payer = models.ForeignKey(
        Payer,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="students",
        verbose_name=_("payeur"),
    )
    created_at = models.DateTimeField(_("créé le"), auto_now_add=True)

    class Meta:
        verbose_name = _("élève")
        verbose_name_plural = _("élèves")
        ordering = ("last_name", "first_name")

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def reference_name(self) -> str:
        """Name matched against bank transfers: the payer's, else the student's."""
        if self.payer is not None:
            return self.payer.reference_name
        return self.payment_reference_name or self.full_name

    def clean(self) -> None:
        errors: dict[str, ValidationError] = {}
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            errors["end_date"] = ValidationError(
                _("La date de fin doit être postérieure ou égale à la date de début."),
                code="end_before_start",
            )
        if self.status == self.Status.ENDED and self.end_date is None:
            errors["end_date"] = ValidationError(
                _("Un élève terminé doit avoir une date de fin."),
                code="ended_without_end_date",
            )
        if self.status == self.Status.PAUSED:
            errors["status"] = ValidationError(
                _("Le statut « en pause » se déduit des pauses de l'élève."),
                code="paused_is_derived",
            )
        if self.payer is not None and self.payer.profession_id != self.profession_id:
            errors["payer"] = ValidationError(
                _("Le payeur n'appartient pas à cette activité."),
                code="payer_profession_mismatch",
            )
        if errors:
            raise ValidationError(errors)


class StudentPause(ProfessionOwnedModel):
    """A period during which a student takes no lessons (« pause »).

    No payment is expected for a month lying entirely within a pause; a month
    only partly covered stays due in full, since nothing is prorated. `ends_on`
    stays empty while the return date is unknown. Pauses of a student never
    overlap; that rule needs the sibling pauses and lives in the services.
    """

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="pauses",
        verbose_name=_("élève"),
    )
    starts_on = models.DateField(_("début de la pause"))
    ends_on = models.DateField(_("fin de la pause"), null=True, blank=True)

    class Meta:
        verbose_name = _("pause")
        verbose_name_plural = _("pauses")
        ordering = ("-starts_on", "-pk")
        constraints = (
            models.CheckConstraint(
                condition=Q(ends_on__isnull=True) | Q(ends_on__gte=F("starts_on")),
                name="student_pause_ends_after_start",
                violation_error_message=_(
                    "La fin de la pause doit être postérieure ou égale à son début."
                ),
            ),
        )

    def __str__(self) -> str:
        if self.ends_on is None:
            return f"{self.starts_on:%d.%m.%Y} -"
        return f"{self.starts_on:%d.%m.%Y} - {self.ends_on:%d.%m.%Y}"

    @property
    def is_open(self) -> bool:
        return self.ends_on is None

    def covers_day(self, day: date) -> bool:
        if day < self.starts_on:
            return False
        return self.ends_on is None or day <= self.ends_on

    def covers_whole_month(self, month: date) -> bool:
        """Whether every day of `month` lies within the pause."""
        if self.starts_on > month:
            return False
        if self.ends_on is None:
            return True
        last_day_of_month = month_add(month, 1) - timedelta(days=1)
        return self.ends_on >= last_day_of_month

    def clean(self) -> None:
        errors: dict[str, ValidationError] = {}
        if (
            self.student_id is not None
            and self.student.profession_id != self.profession_id
        ):
            errors["student"] = ValidationError(
                _("L'élève n'appartient pas à cette activité."),
                code="student_profession_mismatch",
            )
        if (
            self.starts_on is not None
            and self.ends_on is not None
            and self.ends_on < self.starts_on
        ):
            errors["ends_on"] = ValidationError(
                _("La fin de la pause doit être postérieure ou égale à son début."),
                code="ends_before_start",
            )
        if errors:
            raise ValidationError(errors)


class PlanAssignment(ProfessionOwnedModel):
    """A plan assigned to a student or to a payer from a given month.

    Successive assignments of the same target form its plan history
    (« changements de formule »). `starts_on` and `ends_on` are first days of
    months; `ends_on` is the last month covered, inclusive, or empty while the
    assignment is open. A plan assigned to a payer is a family plan.
    """

    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="assignments",
        verbose_name=_("formule"),
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="plan_assignments",
        verbose_name=_("élève"),
    )
    payer = models.ForeignKey(
        Payer,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="plan_assignments",
        verbose_name=_("payeur"),
    )
    starts_on = models.DateField(_("premier mois"), validators=[validate_month_start])
    ends_on = models.DateField(
        _("dernier mois"), null=True, blank=True, validators=[validate_month_start]
    )

    class Meta:
        verbose_name = _("attribution de formule")
        verbose_name_plural = _("attributions de formule")
        ordering = ("-starts_on", "-pk")
        constraints = (
            models.CheckConstraint(
                condition=(
                    Q(student__isnull=False, payer__isnull=True)
                    | Q(student__isnull=True, payer__isnull=False)
                ),
                name="plan_assignment_single_target",
                violation_error_message=_(
                    "Une attribution concerne soit un élève, soit un payeur."
                ),
            ),
            models.CheckConstraint(
                condition=Q(ends_on__isnull=True) | Q(ends_on__gte=F("starts_on")),
                name="plan_assignment_ends_after_start",
                violation_error_message=_(
                    "Le dernier mois doit être postérieur ou égal au premier."
                ),
            ),
            models.UniqueConstraint(
                fields=("student", "starts_on"),
                condition=Q(student__isnull=False),
                name="unique_student_plan_assignment_per_month",
                violation_error_message=_(
                    "Cet élève a déjà une attribution commençant ce mois-là."
                ),
            ),
            models.UniqueConstraint(
                fields=("payer", "starts_on"),
                condition=Q(payer__isnull=False),
                name="unique_payer_plan_assignment_per_month",
                violation_error_message=_(
                    "Ce payeur a déjà une attribution commençant ce mois-là."
                ),
            ),
        )

    def __str__(self) -> str:
        return f"{self.plan} ({self.starts_on:%m.%Y})"

    @property
    def target(self) -> Student | Payer:
        if self.student is not None:
            return self.student
        if self.payer is not None:
            return self.payer
        raise ValueError("A plan assignment must have a student or a payer.")

    @property
    def is_open(self) -> bool:
        return self.ends_on is None

    def clean(self) -> None:
        has_student = self.student_id is not None
        has_payer = self.payer_id is not None
        if has_student == has_payer:
            raise ValidationError(
                _("Une attribution concerne soit un élève, soit un payeur."),
                code="single_target",
            )
        errors: dict[str, ValidationError] = {}
        target_field = "student" if has_student else "payer"
        if self.target.profession_id != self.profession_id:
            errors[target_field] = ValidationError(
                _("La cible n'appartient pas à cette activité."),
                code="target_profession_mismatch",
            )
        if self.plan_id is not None:
            if self.plan.profession_id != self.profession_id:
                errors["plan"] = ValidationError(
                    _("La formule n'appartient pas à cette activité."),
                    code="plan_profession_mismatch",
                )
            elif has_payer and not self.plan.is_monthly:
                errors["plan"] = ValidationError(
                    _("Seule une formule mensuelle peut être attribuée à un payeur."),
                    code="family_plan_not_monthly",
                )
        if (
            self.starts_on is not None
            and self.ends_on is not None
            and self.ends_on < self.starts_on
        ):
            errors["ends_on"] = ValidationError(
                _("Le dernier mois doit être postérieur ou égal au premier."),
                code="ends_before_start",
            )
        if errors:
            raise ValidationError(errors)
