import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator

UserRef = settings.AUTH_USER_MODEL


class TimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserProfile(TimeStampedModel):
    user = models.OneToOneField(UserRef, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    pin_code = models.CharField(max_length=12, blank=True)

    blocked_until = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Profile<{self.user_id}>"

    @property
    def is_blocked_from_messages(self):
        from django.utils import timezone
        return self.blocked_until and self.blocked_until > timezone.now()



class ProductCategory(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    class Condition(models.TextChoices):
        NEW = "new", "New"
        LIKE_NEW = "like_new", "Like New"
        USED = "used", "Used"

    seller = models.ForeignKey(UserRef, on_delete=models.CASCADE, related_name="products")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    currency = models.CharField(max_length=3, default="INR")
    condition = models.CharField(
        max_length=20, choices=Condition.choices, default=Condition.USED
    )
    is_active = models.BooleanField(default=True)
    view_count = models.PositiveIntegerField(default=0)

    # seller-provided location
    location_city = models.CharField(max_length=120, blank=True)
    location_state = models.CharField(max_length=120, blank=True)
    location_country = models.CharField(max_length=120, blank=True)

    # extras
    category = models.ForeignKey(
        ProductCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="products"
    )
    min_offer_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.currency} {self.price})"


class ProductImage(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/%Y/%m/%d/")
    alt_text = models.CharField(max_length=150, blank=True)
    sort_order = models.PositiveIntegerField(default=0)


class Block(TimeStampedModel):
    blocker = models.ForeignKey(UserRef, on_delete=models.CASCADE, related_name="blocked")
    blocked = models.ForeignKey(UserRef, on_delete=models.CASCADE, related_name="blocked_by")

    class Meta:
        unique_together = (("blocker", "blocked"),)


class Negotiation(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        CANCELED = "canceled", "Canceled"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="negotiations")
    seller = models.ForeignKey(UserRef, on_delete=models.CASCADE, related_name="negotiations_as_seller")
    buyer = models.ForeignKey(UserRef, on_delete=models.CASCADE, related_name="negotiations_as_buyer")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    last_offer_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    def is_party(self, user):
        uid = getattr(user, "id", user)
        return uid in {getattr(self.seller, "id", self.seller), getattr(self.buyer, "id", self.buyer)}


class OfferRound(TimeStampedModel):
    negotiation = models.ForeignKey(Negotiation, on_delete=models.CASCADE, related_name="rounds")
    offered_by = models.ForeignKey(UserRef, on_delete=models.CASCADE)
    price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    message = models.CharField(max_length=300, blank=True)


class Deal(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        SHIPPED = "shipped", "Shipped"
        COMPLETED = "completed", "Completed"
        CANCELED = "canceled", "Canceled"

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="deals")
    buyer = models.ForeignKey(UserRef, on_delete=models.PROTECT, related_name="purchases")
    seller = models.ForeignKey(UserRef, on_delete=models.PROTECT, related_name="sales")
    agreed_price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)


class AnalyticsEvent(TimeStampedModel):
    class Type(models.TextChoices):
        PRODUCT_VIEW = "product_view", "Product View"
        PRODUCT_CLICK = "product_click", "Product Click"
        OFFER_CREATED = "offer_created", "Offer Created"
        OFFER_ACCEPTED = "offer_accepted", "Offer Accepted"
        WISHLIST_ADD = "wishlist_add", "Wishlist Add"

    event_type = models.CharField(max_length=30, choices=Type.choices)
    user = models.ForeignKey(UserRef, on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    negotiation = models.ForeignKey(Negotiation, on_delete=models.SET_NULL, null=True, blank=True)

    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    referrer = models.TextField(blank=True)

    country = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)

    extra = models.JSONField(default=dict, blank=True)


class WishlistItem(TimeStampedModel):
    user = models.ForeignKey(UserRef, on_delete=models.CASCADE, related_name="wishlist_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="wishlisted_by")

    class Meta:
        unique_together = (("user", "product"),)


class NegotiationMessage(models.Model):
    negotiation = models.ForeignKey(
        Negotiation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(UserRef, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class MessageReport(models.Model):
    message = models.ForeignKey(
        NegotiationMessage, on_delete=models.CASCADE, related_name="reports"
    )
    reporter = models.ForeignKey(UserRef, on_delete=models.CASCADE)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("message", "reporter")



class UserBlock(models.Model):
    negotiation = models.ForeignKey(Negotiation, on_delete=models.CASCADE, related_name="user_blocks")
    blocked_user = models.ForeignKey(UserRef, on_delete=models.CASCADE, related_name="blocked_in_negotiations")
    blocked_by = models.ForeignKey(UserRef, on_delete=models.CASCADE, related_name="blocked_others_in_negotiations")
    blocked_until = models.DateTimeField()

    class Meta:
        unique_together = ("negotiation", "blocked_user", "blocked_by")

