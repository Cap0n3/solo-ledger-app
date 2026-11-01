"""Obviously fake students, plans and payers for development.

Called by `manage.py seed` once per profession. Names are fixed (no Faker,
which is a development-only dependency) and prefixed with [TEST].
"""

import datetime
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from django.core.management.base import OutputWrapper
from django.db import transaction

from core.apps.accounts.models import Profession
from core.apps.accounts.services import lesson_year_create

from .models import Payer, Plan, Student
from .selectors import plan_list
from .services import payer_create, plan_assign, plan_create, student_create

TEST_PREFIX = "[TEST] "
FAMILY_PLAN_STARTS_ON = datetime.date(2026, 9, 1)
LESSON_YEARS = (
    (datetime.date(2025, 9, 1), datetime.date(2026, 7, 1)),
    (datetime.date(2026, 9, 1), datetime.date(2027, 7, 1)),
)


@dataclass(frozen=True)
class SeedPlan:
    name: str
    price: Decimal
    kind: Plan.Kind = Plan.Kind.MONTHLY


@dataclass(frozen=True)
class SeedPayer:
    name: str
    payment_reference_name: str
    family_plan_name: str | None = None


@dataclass(frozen=True)
class SeedStudent:
    first_name: str
    last_name: str
    start_date: datetime.date
    plan_name: str | None = None
    status: Student.Status = Student.Status.ACTIVE
    end_date: datetime.date | None = None
    payer_name: str | None = None


@dataclass(frozen=True)
class SeedCatalog:
    plans: tuple[SeedPlan, ...]
    payers: tuple[SeedPayer, ...]
    students: tuple[SeedStudent, ...]


GUITAR_CATALOG = SeedCatalog(
    plans=(
        SeedPlan("Nouvelle formule hebdomadaire", Decimal("280")),
        SeedPlan("Ancienne formule hebdomadaire", Decimal("260")),
        SeedPlan("Formule bimensuelle", Decimal("160")),
    ),
    payers=(SeedPayer("Famille Martin", "MARTIN JEAN"),),
    students=(
        SeedStudent(
            "Alice",
            "Dupont",
            datetime.date(2025, 9, 1),
            "Ancienne formule hebdomadaire",
        ),
        SeedStudent(
            "Bruno",
            "Martin",
            datetime.date(2026, 9, 1),
            "Nouvelle formule hebdomadaire",
            payer_name="Famille Martin",
        ),
        SeedStudent(
            "Chloé",
            "Martin",
            datetime.date(2026, 9, 1),
            "Formule bimensuelle",
            payer_name="Famille Martin",
        ),
        SeedStudent(
            "David",
            "Rochat",
            datetime.date(2025, 10, 1),
            "Ancienne formule hebdomadaire",
        ),
        SeedStudent(
            "Emma", "Favre", datetime.date(2026, 9, 15), "Nouvelle formule hebdomadaire"
        ),
        SeedStudent(
            "Félix",
            "Moret",
            datetime.date(2026, 10, 1),
            "Formule bimensuelle",
            status=Student.Status.PAUSED,
        ),
        SeedStudent(
            "Gaëlle",
            "Perrin",
            datetime.date(2025, 9, 1),
            "Ancienne formule hebdomadaire",
            status=Student.Status.ENDED,
            end_date=datetime.date(2026, 6, 30),
        ),
        SeedStudent(
            "Hugo", "Blanc", datetime.date(2026, 9, 1), "Nouvelle formule hebdomadaire"
        ),
        SeedStudent(
            "Inès", "Roux", datetime.date(2026, 11, 1), "Nouvelle formule hebdomadaire"
        ),
        SeedStudent(
            "Jules", "Girard", datetime.date(2026, 9, 1), "Formule bimensuelle"
        ),
        SeedStudent(
            "Karim",
            "Mercier",
            datetime.date(2025, 9, 1),
            "Ancienne formule hebdomadaire",
        ),
        SeedStudent("Nora", "Vuille", datetime.date(2026, 9, 1)),
    ),
)

SINGING_CATALOG = SeedCatalog(
    plans=(
        SeedPlan("Nouvelle formule hebdomadaire", Decimal("340")),
        SeedPlan("Ancienne formule hebdomadaire", Decimal("320")),
        SeedPlan("Plus ancienne formule hebdomadaire", Decimal("300")),
        SeedPlan("Formule famille", Decimal("420")),
        SeedPlan("Formule bimensuelle", Decimal("180")),
        SeedPlan("Première ancienne formule bimensuelle", Decimal("170")),
        SeedPlan("Deuxième ancienne formule bimensuelle", Decimal("150")),
        SeedPlan("Formule à la carte", Decimal("90"), Plan.Kind.SINGLE_LESSON),
    ),
    payers=(
        SeedPayer("Famille Rossi", "ROSSI MARCO", family_plan_name="Formule famille"),
        SeedPayer("Famille Keller", "KELLER ANNA"),
    ),
    students=(
        SeedStudent(
            "Léa", "Rossi", datetime.date(2026, 9, 1), payer_name="Famille Rossi"
        ),
        SeedStudent(
            "Marco",
            "Rossi",
            datetime.date(2026, 9, 1),
            "Formule à la carte",
            payer_name="Famille Rossi",
        ),
        SeedStudent(
            "Anna",
            "Keller",
            datetime.date(2025, 9, 1),
            "Ancienne formule hebdomadaire",
            payer_name="Famille Keller",
        ),
        SeedStudent(
            "Tim",
            "Keller",
            datetime.date(2026, 9, 1),
            "Formule bimensuelle",
            payer_name="Famille Keller",
        ),
        SeedStudent(
            "Olivia",
            "Steiner",
            datetime.date(2025, 9, 1),
            "Plus ancienne formule hebdomadaire",
        ),
        SeedStudent(
            "Paul", "Dubois", datetime.date(2026, 9, 1), "Nouvelle formule hebdomadaire"
        ),
        SeedStudent(
            "Quentin",
            "Berger",
            datetime.date(2026, 10, 1),
            "Formule bimensuelle",
            status=Student.Status.PAUSED,
        ),
        SeedStudent(
            "Rania",
            "Meyer",
            datetime.date(2025, 9, 1),
            "Première ancienne formule bimensuelle",
        ),
        SeedStudent(
            "Sofia",
            "Lambert",
            datetime.date(2025, 9, 1),
            "Deuxième ancienne formule bimensuelle",
            status=Student.Status.ENDED,
            end_date=datetime.date(2026, 7, 31),
        ),
        SeedStudent("Théo", "Gasser", datetime.date(2026, 9, 1), "Formule à la carte"),
        SeedStudent(
            "Una",
            "Baumann",
            datetime.date(2026, 11, 1),
            "Nouvelle formule hebdomadaire",
        ),
        SeedStudent("Victor", "Haas", datetime.date(2026, 9, 1)),
    ),
)

CATALOGS = {"guitar": GUITAR_CATALOG, "singing": SINGING_CATALOG}


def _ascii_slug(value: str) -> str:
    """Lower-case ASCII for example.com addresses (accents are not allowed)."""
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


@transaction.atomic
def seed_profession_students(
    *, profession: Profession, catalog_name: str, stdout: OutputWrapper
) -> None:
    """Create the plans, lesson years, payers and students of one profession.

    Idempotent: a profession that already has plans is left untouched.
    """
    if plan_list(profession=profession).exists():
        stdout.write(f"Students of '{profession.name}' already seeded")
        return
    catalog = CATALOGS[catalog_name]
    for first_month, last_month in LESSON_YEARS:
        lesson_year_create(
            profession=profession, first_month=first_month, last_month=last_month
        )
    plans: dict[str, Plan] = {}
    for seed_plan in catalog.plans:
        plans[seed_plan.name] = plan_create(
            profession=profession,
            name=seed_plan.name,
            description="",
            price=seed_plan.price,
            kind=seed_plan.kind,
        )
    payers: dict[str, Payer] = {}
    for seed_payer in catalog.payers:
        payer = payer_create(
            profession=profession,
            name=TEST_PREFIX + seed_payer.name,
            payment_reference_name=seed_payer.payment_reference_name,
            email=f"{_ascii_slug(seed_payer.name).replace(' ', '.')}@example.com",
            phone="",
            notes="",
        )
        payers[seed_payer.name] = payer
        if seed_payer.family_plan_name is not None:
            plan_assign(
                plan=plans[seed_payer.family_plan_name],
                starts_on=FAMILY_PLAN_STARTS_ON,
                payer=payer,
            )
    for seed_student in catalog.students:
        plan = plans[seed_student.plan_name] if seed_student.plan_name else None
        student_payer = (
            payers[seed_student.payer_name] if seed_student.payer_name else None
        )
        email_slug = _ascii_slug(f"{seed_student.first_name}.{seed_student.last_name}")
        student_create(
            profession=profession,
            first_name=TEST_PREFIX + seed_student.first_name,
            last_name=seed_student.last_name,
            email=f"{email_slug}@example.com",
            phone="",
            notes="",
            start_date=seed_student.start_date,
            end_date=seed_student.end_date,
            status=seed_student.status,
            payment_reference_name="",
            payer=student_payer,
            plan=plan,
        )
    stdout.write(
        f"Seeded '{profession.name}': {len(catalog.plans)} plans, "
        f"{len(LESSON_YEARS)} lesson years, {len(catalog.payers)} payers, "
        f"{len(catalog.students)} students"
    )
