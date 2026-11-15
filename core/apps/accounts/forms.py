from typing import Self

from django import forms
from django.contrib.auth import forms as auth_forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _

from core.utils.forms import MonthField

from .models import PAYMENT_DUE_DAY_MAX, LessonYear, Profession, User

# Widgets carry the Bootstrap classes so templates stay free of per-field markup.

AVATAR_MAX_BYTES = 2 * 1024 * 1024
AVATAR_EXTENSIONS = ("jpg", "jpeg", "png", "webp")


class LoginForm(auth_forms.AuthenticationForm):
    username = auth_forms.UsernameField(
        label=_("Nom d'utilisateur"),
        widget=forms.TextInput(
            attrs={
                "autofocus": True,
                "autocomplete": "username",
                "class": "form-control",
            }
        ),
    )
    password = forms.CharField(
        label=_("Mot de passe"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "current-password", "class": "form-control"}
        ),
    )


class PasswordChangeForm(auth_forms.PasswordChangeForm):
    old_password = forms.CharField(
        label=_("Mot de passe actuel"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autofocus": True,
                "autocomplete": "current-password",
                "class": "form-control",
            }
        ),
    )
    new_password1 = forms.CharField(
        label=_("Nouveau mot de passe"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password", "class": "form-control"}
        ),
        help_text=password_validation.password_validators_help_text_html(),
    )
    new_password2 = forms.CharField(
        label=_("Confirmation du nouveau mot de passe"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password", "class": "form-control"}
        ),
    )


class AvatarForm(forms.Form):
    avatar = forms.ImageField(
        label=_("Image"),
        help_text=_("JPEG, PNG ou WebP, 2 Mo au maximum."),
        validators=[FileExtensionValidator(AVATAR_EXTENSIONS)],
        widget=forms.FileInput(
            attrs={
                "class": "form-control",
                "accept": "image/jpeg,image/png,image/webp",
            }
        ),
    )

    def clean_avatar(self) -> UploadedFile[bytes]:
        avatar: UploadedFile[bytes] = self.cleaned_data["avatar"]
        if avatar.size is not None and avatar.size > AVATAR_MAX_BYTES:
            raise ValidationError(_("L'image dépasse 2 Mo."))
        return avatar


class ProfileForm(forms.Form):
    # Both names are optional, like on the user model: the interface falls back
    # to the username when the first name is empty.
    first_name = forms.CharField(
        label=_("Prénom"),
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "autocomplete": "given-name"}
        ),
    )
    last_name = forms.CharField(
        label=_("Nom"),
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "autocomplete": "family-name"}
        ),
    )

    @classmethod
    def for_user(cls, user: User) -> Self:
        """An unbound form showing the user's current names."""
        return cls(initial={"first_name": user.first_name, "last_name": user.last_name})


class LessonYearForm(forms.Form):
    first_month = MonthField(label=_("Premier mois facturé"))
    last_month = MonthField(
        label=_("Dernier mois facturé"),
        help_text=_(
            "Une année de cours couvre au plus douze mois, août non compris en général."
        ),
    )

    @classmethod
    def for_lesson_year(cls, lesson_year: LessonYear) -> Self:
        return cls(
            initial={
                "first_month": lesson_year.first_month,
                "last_month": lesson_year.last_month,
            }
        )


class PaymentDueDayForm(forms.Form):
    payment_due_day = forms.IntegerField(
        label=_("Jour limite de paiement"),
        min_value=1,
        max_value=PAYMENT_DUE_DAY_MAX,
        help_text=_(
            "Un mois qui n'est pas entièrement payé ce jour-là est en retard. "
            "Modifier ce jour recalcule aussi le retard des mois passés."
        ),
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    @classmethod
    def for_profession(cls, profession: Profession) -> Self:
        return cls(initial={"payment_due_day": profession.payment_due_day})
