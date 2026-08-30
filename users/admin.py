from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from users.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (("Rol", {"fields": ("role",)}),)
    list_display = DjangoUserAdmin.list_display + ("role",)
    list_filter = DjangoUserAdmin.list_filter + ("role",)
