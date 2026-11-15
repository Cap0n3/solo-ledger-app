from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from core.utils.forms import add_service_errors

from .decorators import profession_required
from .forms import (
    AvatarForm,
    LessonYearForm,
    LoginForm,
    PasswordChangeForm,
    PaymentDueDayForm,
    ProfileForm,
)
from .selectors import lesson_year_get, lesson_year_list
from .services import (
    lesson_year_create,
    lesson_year_update,
    profession_payment_due_day_update,
    user_avatar_remove,
    user_avatar_update,
    user_profile_update,
)
from .types import ProfessionHttpRequest


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = PasswordChangeForm
    success_url = reverse_lazy("accounts:password_change_done")

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["page_title"] = _("Changer de mot de passe")
        return context


class PasswordChangeDoneView(auth_views.PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["page_title"] = _("Mot de passe modifié")
        return context


def _settings_response(
    request: ProfessionHttpRequest,
    *,
    profile_form: ProfileForm,
    avatar_form: AvatarForm,
    payment_due_day_form: PaymentDueDayForm | None = None,
) -> HttpResponse:
    if payment_due_day_form is None:
        payment_due_day_form = PaymentDueDayForm.for_profession(request.profession)
    context = {
        "payment_due_day_form": payment_due_day_form,
        "page_title": _("Paramètres"),
        "page_subtitle": _("Informations du compte et de l'activité"),
        "profile_form": profile_form,
        "avatar_form": avatar_form,
        "lesson_years": lesson_year_list(profession=request.profession),
    }
    return render(request, "accounts/settings.html", context)


@profession_required
def settings_view(request: ProfessionHttpRequest) -> HttpResponse:
    """Account settings. Business settings arrive in later milestones."""
    return _settings_response(
        request,
        profile_form=ProfileForm.for_user(request.user),
        avatar_form=AvatarForm(),
    )


@profession_required
@require_POST
def profile_update_view(request: ProfessionHttpRequest) -> HttpResponse:
    profile_form = ProfileForm(request.POST)
    if profile_form.is_valid():
        user_profile_update(
            user=request.user,
            first_name=profile_form.cleaned_data["first_name"],
            last_name=profile_form.cleaned_data["last_name"],
        )
        messages.success(request, _("Profil mis à jour."))
        return redirect("accounts:settings")
    return _settings_response(
        request, profile_form=profile_form, avatar_form=AvatarForm()
    )


@profession_required
@require_POST
def avatar_update_view(request: ProfessionHttpRequest) -> HttpResponse:
    avatar_form = AvatarForm(request.POST, request.FILES)
    if avatar_form.is_valid():
        user_avatar_update(user=request.user, avatar=avatar_form.cleaned_data["avatar"])
        messages.success(request, _("Avatar mis à jour."))
        return redirect("accounts:settings")
    return _settings_response(
        request,
        profile_form=ProfileForm.for_user(request.user),
        avatar_form=avatar_form,
    )


@profession_required
@require_POST
def avatar_remove_view(request: ProfessionHttpRequest) -> HttpResponse:
    user_avatar_remove(user=request.user)
    messages.success(request, _("Avatar supprimé."))
    return redirect("accounts:settings")


@profession_required
@require_POST
def payment_due_day_update_view(request: ProfessionHttpRequest) -> HttpResponse:
    payment_due_day_form = PaymentDueDayForm(request.POST)
    if payment_due_day_form.is_valid():
        profession_payment_due_day_update(
            profession=request.profession,
            payment_due_day=payment_due_day_form.cleaned_data["payment_due_day"],
        )
        messages.success(request, _("Jour limite de paiement mis à jour."))
        return redirect("accounts:settings")
    return _settings_response(
        request,
        profile_form=ProfileForm.for_user(request.user),
        avatar_form=AvatarForm(),
        payment_due_day_form=payment_due_day_form,
    )


@profession_required
def lesson_year_create_view(request: ProfessionHttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = LessonYearForm(request.POST)
        if form.is_valid():
            try:
                lesson_year_create(
                    profession=request.profession,
                    first_month=form.cleaned_data["first_month"],
                    last_month=form.cleaned_data["last_month"],
                )
            except ValidationError as error:
                add_service_errors(form, error)
            else:
                messages.success(request, _("Année de cours créée."))
                return redirect("accounts:settings")
    else:
        form = LessonYearForm()
    context = {
        "page_title": _("Nouvelle année de cours"),
        "page_subtitle": _("Paramètres"),
        "form": form,
    }
    return render(request, "accounts/lesson_year_form.html", context)


@profession_required
def lesson_year_update_view(
    request: ProfessionHttpRequest, lesson_year_id: int
) -> HttpResponse:
    lesson_year = lesson_year_get(
        profession=request.profession, lesson_year_id=lesson_year_id
    )
    if request.method == "POST":
        form = LessonYearForm(request.POST)
        if form.is_valid():
            try:
                lesson_year_update(
                    lesson_year=lesson_year,
                    first_month=form.cleaned_data["first_month"],
                    last_month=form.cleaned_data["last_month"],
                )
            except ValidationError as error:
                add_service_errors(form, error)
            else:
                messages.success(request, _("Année de cours mise à jour."))
                return redirect("accounts:settings")
    else:
        form = LessonYearForm.for_lesson_year(lesson_year)
    context = {
        "page_title": lesson_year.name,
        "page_subtitle": _("Modifier l'année de cours"),
        "form": form,
    }
    return render(request, "accounts/lesson_year_form.html", context)
