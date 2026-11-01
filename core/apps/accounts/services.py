from django.core.files.base import File

from .models import Profession, User


def user_create(
    *,
    username: str,
    password: str,
    first_name: str = "",
    email: str = "",
    is_superuser: bool = False,
) -> User:
    if is_superuser:
        return User.objects.create_superuser(
            username=username, password=password, first_name=first_name, email=email
        )
    return User.objects.create_user(
        username=username, password=password, first_name=first_name, email=email
    )


def user_profile_update(*, user: User, first_name: str, last_name: str) -> User:
    user.first_name = first_name
    user.last_name = last_name
    user.save(update_fields=["first_name", "last_name"])
    return user


def user_avatar_update(*, user: User, avatar: File[bytes]) -> User:
    """Replace the user's avatar. The previous file is removed from storage."""
    if user.avatar:
        user.avatar.delete(save=False)
    user.avatar = avatar
    user.save(update_fields=["avatar"])
    return user


def user_avatar_remove(*, user: User) -> User:
    """Delete the avatar file and clear the field. No avatar is not an error."""
    if user.avatar:
        user.avatar.delete(save=False)
        user.save(update_fields=["avatar"])
    return user


def profession_create(*, user: User, name: str) -> Profession:
    profession = Profession(user=user, name=name)
    profession.full_clean()
    profession.save()
    return profession
