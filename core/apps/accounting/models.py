from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from core.apps.accounts.models import ProfessionOwnedModel
from core.apps.students.models import Payer, Plan, Student
from core.utils.months import validate_month_start


class PaymentMethod(models.TextChoices):
    """Fixed list of payment methods; it is not editable in the application."""

    BANK_TRANSFER = "bank_transfer", _("Virement bancaire")
    TWINT = "twint", _("TWINT")
    CASH = "cash", _("Espèces")
    OTHER = "other", _("Autre")


class ExpectedPayment(ProfessionOwnedModel):
    """The amount expected for one billed month from a student or a payer.

    Created automatically from the monthly plan in effect. `amount` is a
    snapshot: changing the plan's price never rewrites it. Whether the month is
    paid, partially paid, unpaid or late is computed from its allocations and
    the payment due day; only the cancellation is stored. `is_due` turns false
    when the month is kept (paid, cancelled or edited by hand) although the
    student's dates, pauses or plan no longer make it due.
    """

    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="expected_payments",
        verbose_name=_("élève"),
    )
    payer = models.ForeignKey(
        Payer,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="expected_payments",
        verbose_name=_("payeur"),
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="expected_payments",
        verbose_name=_("formule"),
    )
    month = models.DateField(_("mois"), validators=[validate_month_start])
    amount = models.DecimalField(
        _("montant attendu"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    is_amount_manual = models.BooleanField(
        _("montant modifié à la main"), default=False
    )
    is_cancelled = models.BooleanField(_("annulé"), default=False)
    cancellation_reason = models.CharField(
        _("motif d'annulation"), max_length=200, blank=True
    )
    is_due = models.BooleanField(_("dû"), default=True)
    created_at = models.DateTimeField(_("créé le"), auto_now_add=True)

    class Meta:
        verbose_name = _("paiement attendu")
        verbose_name_plural = _("paiements attendus")
        ordering = ("month", "pk")
        constraints = (
            models.CheckConstraint(
                condition=(
                    Q(student__isnull=False, payer__isnull=True)
                    | Q(student__isnull=True, payer__isnull=False)
                ),
                name="expected_payment_single_target",
                violation_error_message=_(
                    "Un paiement attendu concerne soit un élève, soit un payeur."
                ),
            ),
            models.UniqueConstraint(
                fields=("student", "month"),
                condition=Q(student__isnull=False),
                name="unique_student_expected_payment_per_month",
            ),
            models.UniqueConstraint(
                fields=("payer", "month"),
                condition=Q(payer__isnull=False),
                name="unique_payer_expected_payment_per_month",
            ),
        )

    def __str__(self) -> str:
        return f"{self.month:%m.%Y} ({self.amount})"

    @property
    def target(self) -> Student | Payer:
        if self.student is not None:
            return self.student
        if self.payer is not None:
            return self.payer
        raise ValueError("An expected payment must have a student or a payer.")

    @property
    def due_date(self) -> date:
        return self.profession.payment_due_date(self.month)

    def clean(self) -> None:
        has_student = self.student_id is not None
        has_payer = self.payer_id is not None
        if has_student == has_payer:
            raise ValidationError(
                _("Un paiement attendu concerne soit un élève, soit un payeur."),
                code="single_target",
            )
        errors: dict[str, ValidationError] = {}
        target_field = "student" if has_student else "payer"
        if self.target.profession_id != self.profession_id:
            errors[target_field] = ValidationError(
                _("La cible n'appartient pas à cette activité."),
                code="target_profession_mismatch",
            )
        if self.plan_id is not None and self.plan.profession_id != self.profession_id:
            errors["plan"] = ValidationError(
                _("La formule n'appartient pas à cette activité."),
                code="plan_profession_mismatch",
            )
        if errors:
            raise ValidationError(errors)


class Payment(ProfessionOwnedModel):
    """Money actually received (« paiement », « recette »).

    A monthly payment targets exactly one student, or one payer settling a
    family plan, and is allocated to expected months. A one-off income (single
    lesson, gift voucher) carries a free label, may be linked to a student and
    is never allocated to a month. Either way the income belongs to the fiscal
    year of `received_on`.
    """

    class Kind(models.TextChoices):
        MONTHLY = "monthly", _("Mensualité")
        ONE_OFF = "one_off", _("Recette ponctuelle")

    kind = models.CharField(_("type"), max_length=10, choices=Kind)
    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
        verbose_name=_("élève"),
    )
    payer = models.ForeignKey(
        Payer,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
        verbose_name=_("payeur"),
    )
    received_on = models.DateField(_("date de réception"))
    amount = models.DecimalField(
        _("montant"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    method = models.CharField(
        _("mode de paiement"), max_length=20, choices=PaymentMethod
    )
    label = models.CharField(_("libellé"), max_length=200, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(_("créé le"), auto_now_add=True)

    class Meta:
        verbose_name = _("paiement")
        verbose_name_plural = _("paiements")
        ordering = ("-received_on", "-pk")
        constraints = (
            models.CheckConstraint(
                condition=(
                    Q(kind="monthly", student__isnull=False, payer__isnull=True)
                    | Q(kind="monthly", student__isnull=True, payer__isnull=False)
                    | Q(kind="one_off", payer__isnull=True)
                ),
                name="payment_target_matches_kind",
                violation_error_message=_(
                    "Une mensualité concerne un élève ou un payeur ; une recette "
                    "ponctuelle ne concerne jamais un payeur."
                ),
            ),
        )

    def __str__(self) -> str:
        return f"{self.received_on:%d.%m.%Y} ({self.amount})"

    @property
    def is_one_off(self) -> bool:
        return self.kind == self.Kind.ONE_OFF

    @property
    def fiscal_year(self) -> int:
        """Income belongs to the calendar year in which it was received."""
        return self.received_on.year

    def clean(self) -> None:
        errors: dict[str, ValidationError] = {}
        has_student = self.student_id is not None
        has_payer = self.payer_id is not None
        if self.kind == self.Kind.MONTHLY and has_student == has_payer:
            raise ValidationError(
                _("Une mensualité concerne soit un élève, soit un payeur."),
                code="single_target",
            )
        if self.kind == self.Kind.ONE_OFF:
            if has_payer:
                errors["payer"] = ValidationError(
                    _("Une recette ponctuelle ne concerne jamais un payeur."),
                    code="one_off_with_payer",
                )
            if not self.label.strip():
                errors["label"] = ValidationError(
                    _("Une recette ponctuelle a besoin d'un libellé."),
                    code="one_off_without_label",
                )
        is_student_foreign = (
            self.student is not None
            and self.student.profession_id != self.profession_id
        )
        if is_student_foreign:
            errors["student"] = ValidationError(
                _("L'élève n'appartient pas à cette activité."),
                code="student_profession_mismatch",
            )
        is_payer_foreign = (
            self.payer is not None and self.payer.profession_id != self.profession_id
        )
        if is_payer_foreign and "payer" not in errors:
            errors["payer"] = ValidationError(
                _("Le payeur n'appartient pas à cette activité."),
                code="payer_profession_mismatch",
            )
        if errors:
            raise ValidationError(errors)


class PaymentAllocation(models.Model):
    """The share of a payment that settles one expected month.

    Ownership follows the payment: both sides belong to the same profession and
    to the same student or payer, which the payment services enforce.
    """

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="allocations",
        verbose_name=_("paiement"),
    )
    expected_payment = models.ForeignKey(
        ExpectedPayment,
        on_delete=models.PROTECT,
        related_name="allocations",
        verbose_name=_("paiement attendu"),
    )
    amount = models.DecimalField(
        _("montant attribué"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    class Meta:
        verbose_name = _("attribution de paiement")
        verbose_name_plural = _("attributions de paiement")
        ordering = ("expected_payment__month", "pk")
        constraints = (
            models.UniqueConstraint(
                fields=("payment", "expected_payment"),
                name="unique_allocation_per_payment_and_month",
            ),
        )

    def __str__(self) -> str:
        return f"{self.amount} → {self.expected_payment}"
