from django.contrib import admin
from .models import (
    UserProfile, ProductCategory, Product, ProductImage,
    Block, Negotiation, OfferRound, Deal,
    AnalyticsEvent, WishlistItem
)

# --- Mixins / Base ---
class TimeStampedAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


# --- User Profile ---
@admin.register(UserProfile)
class UserProfileAdmin(TimeStampedAdmin):
    list_display = ("user", "full_name", "phone", "email", "city", "state", "country")
    search_fields = ("user__username", "full_name", "phone", "email", "city", "state")
    list_filter = ("state", "country")


# --- Category ---
@admin.register(ProductCategory)
class ProductCategoryAdmin(TimeStampedAdmin):
    list_display = ("name", "parent")
    search_fields = ("name",)
    list_filter = ("parent",)


# --- Product Images Inline ---
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "alt_text", "sort_order")
    ordering = ("sort_order",)


# --- Product ---
@admin.register(Product)
class ProductAdmin(TimeStampedAdmin):
    list_display = (
        "title", "seller", "price", "currency", "condition",
        "category", "view_count", "is_active", "created_at"
    )
    list_filter = ("is_active", "condition", "currency", "category")
    search_fields = ("title", "description", "seller__username", "location_city", "location_state")
    inlines = [ProductImageInline]
    autocomplete_fields = ("seller", "category")


# --- Block ---
@admin.register(Block)
class BlockAdmin(TimeStampedAdmin):
    list_display = ("blocker", "blocked", "created_at")
    search_fields = ("blocker__username", "blocked__username")


# --- Negotiation ---
class OfferRoundInline(admin.TabularInline):
    model = OfferRound
    extra = 0
    fields = ("offered_by", "price", "message", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Negotiation)
class NegotiationAdmin(TimeStampedAdmin):
    list_display = ("product", "seller", "buyer", "status", "last_offer_price", "created_at")
    list_filter = ("status",)
    search_fields = ("product__title", "seller__username", "buyer__username")
    inlines = [OfferRoundInline]


# --- Deals ---
@admin.register(Deal)
class DealAdmin(TimeStampedAdmin):
    list_display = ("product", "buyer", "seller", "agreed_price", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("product__title", "buyer__username", "seller__username")


# --- Analytics ---
@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(TimeStampedAdmin):
    list_display = ("event_type", "user", "product", "country", "city", "created_at")
    list_filter = ("event_type", "country", "region", "city")
    search_fields = ("user__username", "product__title", "ip", "user_agent")
    readonly_fields = ("extra",)


# --- Wishlist ---
@admin.register(WishlistItem)
class WishlistItemAdmin(TimeStampedAdmin):
    list_display = ("user", "product", "created_at")
    search_fields = ("user__username", "product__title")
    autocomplete_fields = ("user", "product")
