from django.contrib import admin

from .models import Payer, Plan, PlanAssignment, Student


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin[Plan]):
    list_display = ("name", "profession", "kind", "price", "is_archived")
    list_filter = ("profession", "kind", "is_archived")
    search_fields = ("name",)


@admin.register(Payer)
class PayerAdmin(admin.ModelAdmin[Payer]):
    list_display = ("name", "profession", "payment_reference_name")
    list_filter = ("profession",)
    search_fields = ("name", "payment_reference_name")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin[Student]):
    list_display = ("last_name", "first_name", "profession", "status", "start_date")
    list_filter = ("profession", "status")
    search_fields = ("last_name", "first_name", "email", "payment_reference_name")


@admin.register(PlanAssignment)
class PlanAssignmentAdmin(admin.ModelAdmin[PlanAssignment]):
    list_display = ("plan", "student", "payer", "starts_on", "ends_on")
    list_filter = ("profession",)
