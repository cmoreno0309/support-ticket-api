from django.contrib import admin

from tickets.models import Ticket, TicketComment, TicketEvent


class TicketCommentInline(admin.TabularInline):
    model = TicketComment
    extra = 0
    readonly_fields = ["author", "body", "is_internal", "created_at"]
    can_delete = False


class TicketEventInline(admin.TabularInline):
    model = TicketEvent
    extra = 0
    readonly_fields = [
        "actor",
        "event_type",
        "field",
        "old_value",
        "new_value",
        "note",
        "created_at",
    ]
    can_delete = False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "subject",
        "status",
        "priority",
        "created_by",
        "assigned_to",
        "created_at",
    ]
    list_filter = ["status", "priority"]
    search_fields = ["reference", "subject"]
    readonly_fields = ["id", "reference", "created_at", "updated_at"]
    inlines = [TicketCommentInline, TicketEventInline]


@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    list_display = ["ticket", "author", "is_internal", "created_at"]
    list_filter = ["is_internal"]


@admin.register(TicketEvent)
class TicketEventAdmin(admin.ModelAdmin):
    list_display = ["ticket", "event_type", "actor", "created_at"]
    list_filter = ["event_type"]
