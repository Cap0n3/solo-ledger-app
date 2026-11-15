from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def paused_status_to_active(
    apps: Apps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """« En pause » is now derived from `StudentPause`; the stored status of a
    paused student falls back to active. No pause is invented: the dates of
    past pauses were never recorded."""
    student_model = apps.get_model("students", "Student")
    student_model.objects.filter(status="paused").update(status="active")


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0002_studentpause"),
    ]

    operations = [
        migrations.RunPython(paused_status_to_active, migrations.RunPython.noop),
    ]
