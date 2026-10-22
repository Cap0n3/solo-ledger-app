from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from .decorators import profession_required
from .forms import LoginForm, PasswordChangeForm
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


@profession_required
def settings_view(request: ProfessionHttpRequest) -> HttpResponse:
    """Account settings. Business settings arrive in later milestones."""
    context = {
        "page_title": _("Paramètres"),
        "page_subtitle": _("Informations du compte et de l'activité"),
    }
    return render(request, "accounts/settings.html", context)
