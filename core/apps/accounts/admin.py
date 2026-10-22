from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Activity, User

admin.site.register(User, UserAdmin)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin[Activity]):
    list_display = ("name", "user", "created_at")
    list_filter = ("user",)
    search_fields = ("name", "user__username")
