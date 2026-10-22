from django.db.models import QuerySet

from .models import Activity, User


def activity_list(*, user: User) -> QuerySet[Activity]:
    return Activity.objects.filter(user=user)


def activity_current(
    *, user: User, selected_activity_id: int | None
) -> Activity | None:
    """Resolve the activity the user is currently working on.

    The activity selected in the session wins as long as it still belongs to
    the user; otherwise the oldest activity is used so that the fallback stays
    stable when new activities are added later.
    """
    owned_activities = activity_list(user=user)
    if selected_activity_id is not None:
        selected_activity = owned_activities.filter(pk=selected_activity_id).first()
        if selected_activity is not None:
            return selected_activity
    return owned_activities.order_by("created_at", "pk").first()
