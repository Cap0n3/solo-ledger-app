from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Profession, User

admin.site.register(User, UserAdmin)


@admin.register(Profession)
class ProfessionAdmin(admin.ModelAdmin[Profession]):
    list_display = ("name", "user", "created_at")
    list_filter = ("user",)
    search_fields = ("name", "user__username")
