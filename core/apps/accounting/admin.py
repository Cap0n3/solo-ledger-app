from django.contrib import admin

from .models import ExpectedPayment, Payment, PaymentAllocation


@admin.register(ExpectedPayment)
class ExpectedPaymentAdmin(admin.ModelAdmin[ExpectedPayment]):
    list_display = ("month", "student", "payer", "amount", "is_cancelled", "is_due")
    list_filter = ("profession", "is_cancelled", "is_due")


class PaymentAllocationInline(admin.TabularInline[PaymentAllocation, Payment]):
    model = PaymentAllocation
    extra = 0


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin[Payment]):
    list_display = ("received_on", "kind", "student", "payer", "amount", "method")
    list_filter = ("profession", "kind", "method")
    inlines = (PaymentAllocationInline,)
