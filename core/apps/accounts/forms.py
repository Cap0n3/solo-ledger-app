from django import forms
from django.contrib.auth import forms as auth_forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _

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
