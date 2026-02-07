from django.contrib import admin
from .models import UserProfile

# Register your models here.
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "phone", "organization", "job_title", "bio", "address_line1", "address_line2", "city", "state", "postal_code", "country", "date_of_birth", "updated_at")
    search_fields = ("user__username", "organization", "job_title")
    readonly_fields = ("updated_at",)