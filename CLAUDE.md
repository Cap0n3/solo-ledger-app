# CLAUDE.md

## Project

SoloLedger is a Django web app for managing the accounting and students of independent music teaching activities (guitar lessons, singing lessons). Each user owns one or more activities and only ever sees their own data.

`SPECS.md` is the source of truth for features and business rules. Read it before planning any feature. If the spec is ambiguous or contradicts itself, ask before implementing. Do not guess business rules.

## Stack

- Python 3.14 (3.15 once Django officially supports it, from 6.1.3)
- Django 6.1.2 (templates, forms, built-in auth)
- PostgreSQL
- HTMX for partial page updates, Alpine.js for light client-side interactions
- Bootstrap 5.3.8 for styling (SCSS compiled from `core/assets/` with dart-sass, JS bundled with esbuild)
- Docker Compose for dev and prod; VS Code Dev Container for development
- uv for Python dependencies (`pyproject.toml` + `uv.lock`); Node 24 lives inside the Django image for the asset pipeline

Do not add new dependencies (Python or JS) without asking first.

## Commands

All commands run through the Makefile, inside Docker:

```
make setup         # first run: .env, build, start, migrate, assets, seed
make up            # start the stack
make down          # stop the stack
make build         # rebuild the web image (after pyproject.toml / uv.lock / Dockerfile changes)
make run           # Django dev server (from inside the Dev Container)
make migrate       # apply migrations
make migrations    # create migrations
make test          # run the test suite
make lint          # ruff, mypy, djlint, prettier, makemigrations --check
make format        # auto-format all code
make npm           # install JS dependencies when package-lock.json changed
make assets        # build CSS/JS
make assets-watch  # rebuild CSS/JS on change
make seed          # generate fake test data
make shell         # Django shell
make lock          # regenerate uv.lock after editing pyproject.toml (then make build)
make createsuperuser
make reset-db      # drop the database volume
make help          # list all targets
```

The same Makefile works from the host (commands go through `docker compose exec`) and from
inside the Dev Container (commands run directly). `up`, `down`, `build`, `logs` and `reset-db`
are host-only.

Run `make lint` and `make test` before considering a task done.

## Project structure

```
core/                  # Python package: settings module is core.config.settings.*
├── config/            # settings (base, development, production, test), urls, wsgi/asgi
├── apps/              # one Django app per business domain
│   ├── accounts/      # User, Activity, data-separation helpers, seed command
│   ├── students/
│   ├── accounting/
│   ├── bank_imports/
│   └── reports/       # dashboard, statistics, income statement
├── templates/
├── assets/            # SCSS and JS sources
└── static/dist/       # compiled assets (generated, not versioned, do not edit by hand)
```

Apps are referenced by their dotted path (`core.apps.accounts`) and keep their short label
(`accounts`). `DJANGO_SETTINGS_MODULE` is never set in `.env`: `manage.py` defaults to the
development settings and pytest forces the test settings.

## Architecture

We follow the HackSoft Django Styleguide, applied pragmatically:

- **Models**: data, constraints, simple properties. No business workflows.
- **Services** (`services.py`): all writes and business operations. Named `<entity>_<action>`, e.g. `student_create`, `plan_change`, `bank_statement_import`, `payment_match_confirm`.
- **Selectors** (`selectors.py`): non-trivial reads and queries. Named after what they return, e.g. `student_list`, `expected_payments_for_month`.
- **Views**: thin. Parse input, call a service or selector, render. No business logic in views or templates.
- **Forms**: validation of user input only.

Use keyword-only arguments for services and selectors (`def student_create(*, activity: Activity, name: str) -> Student`).

### Bank CSV parsing

The bank export format can change without notice. All parsing lives behind a single parser interface in `bank_imports/parsers/`, which returns normalized transaction objects. Nothing outside the parser module may depend on raw CSV column names.

## Data separation (critical)

- Every business record belongs to an `Activity`, and every `Activity` belongs to a `User`.
  Business models inherit from `accounts.models.ActivityOwnedModel`.
- Views take the current activity from `request.activity`, set by the `activity_required`
  decorator (`accounts/decorators.py`); annotate such views with `ActivityHttpRequest`.
  The current activity is resolved by the `activity_current` selector (session, then oldest).
- Every selector and service takes the user or activity explicitly and filters by it. Never query business models without ownership filtering.
- Views must never fetch objects by ID alone. Use `get_object_or_404` with an ownership filter, through a selector.
- Every feature needs a test proving that one user cannot read or modify another user's data.

## Language rules

- **All code is in English**: models, fields, variables, functions, URL names and URL paths (`/students/`), comments, docstrings, test names, commit messages. Never use French in code.
- **All user-facing text is in French**, wrapped in `gettext_lazy` / `{% translate %}`, including `verbose_name` on models and fields.
- Locale is fr-CH. Currency is CHF only.

### Glossary

Always use these names. Do not invent synonyms.

| French (UI)                  | Code                   |
|------------------------------|------------------------|
| activité                     | `Activity`             |
| élève                        | `Student`              |
| payeur                       | `Payer`                |
| nom de référence paiements   | `payment_reference_name` |
| formule                      | `Plan`                 |
| changement de formule        | `PlanAssignment`       |
| cours à la carte             | `single_lesson`        |
| formule famille              | `family plan` (a `Plan` assigned to a `Payer`) |
| mois annulé                  | `ExpectedPayment` with status `cancelled` |
| arriéré                      | `arrears`              |
| année de cours               | `LessonYear`           |
| année fiscale                | `fiscal_year` (calendar year, `int`) |
| jour limite de paiement      | `payment_due_day`      |
| paiement attendu             | `ExpectedPayment`      |
| paiement / recette           | `Payment` / `income`   |
| écriture comptable           | `LedgerEntry`          |
| mode de paiement             | `PaymentMethod`        |
| dépense                      | `Expense`              |
| label de dépense             | `ExpenseCategory`      |
| relevé bancaire              | `BankStatement`        |
| transaction bancaire         | `BankTransaction`      |
| rapprochement                | `Reconciliation` / `match` |
| compte d'exploitation        | `IncomeStatement`      |
| numéro d'indépendant         | `self_employed_number` |
| tableau de bord              | `dashboard`            |
| activité courante            | `current activity` (`activity_current` selector) |

When a new domain concept appears, add it to this table before using it.

## Code style

- PEP 8, enforced by Ruff (lint + format, line length 88). djLint for templates, Prettier for JS/SCSS.
### Type annotations

- Every function and method is fully annotated: all parameters and the return type, including `-> None`. Enforced by Ruff (`ANN` rules) and checked by mypy with the django-stubs plugin. Tests are exempt from the `ANN` rules.
- Use modern syntax: `str | None`, `list[Student]`, `dict[str, Decimal]`. Never `Optional`, `List` or `Dict` from `typing`. No `from __future__ import annotations`.
- Annotate Django types precisely: `QuerySet[Student]`, `HttpRequest`, `HttpResponse`. Views that require login use a shared `AuthenticatedHttpRequest` type whose `user` is the concrete user model.
- Structured data passed between layers uses frozen dataclasses, never loose dicts (e.g. the bank parser returns `ParsedTransaction` objects; statistics selectors return dataclasses).
- Avoid `Any`. A `# type: ignore[code]` must name the error code and carry a comment explaining why.
- **Explicit and readable over compact.** Prefer clear intermediate variables and plain loops over dense comprehensions or chained one-liners.
- **Exceptions**: narrow `try` blocks, specific exception types, use `try/except/else` when there is code that should run only on success. Never use a bare `except`.
- **Booleans** are phrased positively: `is_paid`, `is_confirmed`, `has_active_plan`. Avoid double negatives in names and return values.
- **Money** is always `Decimal`, stored as `DecimalField(max_digits=10, decimal_places=2)`. Never use `float` for amounts.
- **Dates**: use `datetime.date` for business dates (months, due dates). A billing month is represented by the first day of that month.
- **Comments** explain *why*, not *what*. Business rules get a short docstring referencing the rule.
- Records that carry a price (expected payments, ledger entries) store a snapshot of the amount. Changing a plan's price never rewrites history.

### Lesson year vs fiscal year (critical)

These two periods must never be mixed:

- **Lesson year** (`LessonYear`, e.g. September 2026 to July 2027): used for expected payments, allocation of payments to months, late payments and arrears.
- **Fiscal year** (calendar year): income belongs to the fiscal year of its **received date**, expenses to the year of their **paid date**. Used for the income statement and financial statistics.

A payment received on 2026-12-28 for January 2027 is allocated to January in lesson year 2026-2027, but is 2026 income. Selectors must make the period type explicit in their name or signature (e.g. `income_for_fiscal_year`, `expected_payments_for_lesson_year`).

## Testing

- pytest with pytest-django. Use factories (factory_boy) for test data.
- Tests live in each app under `tests/`, split by layer: `test_models.py`, `test_services.py`, `test_selectors.py`, `test_views.py`.
- Prioritize: business rules, money calculations, payment matching, CSV import edge cases, and data separation between users.
- Do not write trivial tests that only restate Django behavior.
- A task is not done until its tests pass.

## Workflow

- Work one milestone at a time, as planned in plan mode. Do not start work outside the current milestone.
- Within a milestone: models and their tests first, then services/selectors/views and their tests, then templates.
- Keep migrations small and readable. Never edit an applied migration. Never squash or delete migrations without asking.
- If something in the plan turns out to be wrong during implementation, stop and explain rather than silently changing direction.

## Confidential data

- `docs/references/` may contain real bank exports with personal and financial data. Never copy real data into fixtures, tests, seed data, commits, logs or code.
- Use only the anonymized sample CSV for tests and parser development.
- Seed data must be obviously fake (e.g. names prefixed with `[TEST]`, `example.com` emails).
- Never commit `.env` files or secrets.

## Things not to do

- Do not include the web development activity; it is out of scope.
- Do not integrate any bank API.
- Do not generate or send invoices; invoicing happens outside the app.
- Never show one user's data to another user, not even read-only.
- Do not add Celery, React or other infrastructure not listed in the stack.
- Do not delete user data automatically (e.g. students missing from an imported CSV are kept).