from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from .decorators import profession_required
from .forms import AvatarForm, LoginForm, PasswordChangeForm
from .services import user_avatar_remove, user_avatar_update
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
    if request.method == "POST":
        avatar_form = AvatarForm(request.POST, request.FILES)
        if avatar_form.is_valid():
            user_avatar_update(
                user=request.user, avatar=avatar_form.cleaned_data["avatar"]
            )
            messages.success(request, _("Avatar mis à jour."))
            return redirect("accounts:settings")
    else:
        avatar_form = AvatarForm()
    context = {
        "page_title": _("Paramètres"),
        "page_subtitle": _("Informations du compte et de l'activité"),
        "avatar_form": avatar_form,
    }
    return render(request, "accounts/settings.html", context)


@profession_required
@require_POST
def avatar_remove_view(request: ProfessionHttpRequest) -> HttpResponse:
    user_avatar_remove(user=request.user)
    messages.success(request, _("Avatar supprimé."))
    return redirect("accounts:settings")
