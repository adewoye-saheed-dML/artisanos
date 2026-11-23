from django.contrib import admin

from .models import NigerianLGA, NigerianState, NigerianWard, PollingUnit


@admin.register(NigerianState)
class NigerianStateAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "geopolitical_zone")
    search_fields = ("name", "code")


@admin.register(NigerianLGA)
class NigerianLGAAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "code")
    list_filter = ("state",)
    search_fields = ("name", "state__name")


@admin.register(NigerianWard)
class NigerianWardAdmin(admin.ModelAdmin):
    list_display = ("name", "lga", "code")
    list_filter = ("lga__state",)
    search_fields = ("name", "lga__name", "lga__state__name")


@admin.register(PollingUnit)
class PollingUnitAdmin(admin.ModelAdmin):
    list_display = ("pu_code", "name", "ward", "latitude", "longitude")
    list_filter = ("ward__lga__state",)
    search_fields = ("pu_code", "name", "landmark", "ward__name")
