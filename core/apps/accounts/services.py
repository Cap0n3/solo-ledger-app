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


def profession_create(*, user: User, name: str) -> Profession:
    profession = Profession(user=user, name=name)
    profession.full_clean()
    profession.save()
    return profession
