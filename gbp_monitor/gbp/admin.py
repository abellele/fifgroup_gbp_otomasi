"""
admin.py — Django Admin untuk GBP Monitor.
"""

from django.contrib import admin
from .models import FetchRun, LocationSnapshot


@admin.register(FetchRun)
class FetchRunAdmin(admin.ModelAdmin):
    list_display = [
        "id", "run_date", "run_timestamp",
        "total", "verified", "duplicate", "suspended", "unverified",
    ]
    list_filter = ["run_date"]
    ordering = ["-id"]
    readonly_fields = ["run_timestamp"]


@admin.register(LocationSnapshot)
class LocationSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        "id", "run", "store_code", "business_name",
        "status", "coord_status", "fetched_at",
    ]
    list_filter = ["status", "coord_status", "run"]
    search_fields = ["store_code", "business_name", "location_name"]
    raw_id_fields = ["run"]
    ordering = ["-id"]
