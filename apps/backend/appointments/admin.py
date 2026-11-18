from django.contrib import admin

from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ["title", "customer", "appointment_type", "scheduled_at", "status", "location"]
    list_filter = ["status", "appointment_type"]
    search_fields = ["title", "customer__full_name", "location"]
