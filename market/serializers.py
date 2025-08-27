from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import (
    Product, ProductImage, ProductCategory,
    Negotiation, OfferRound, Deal, Block, AnalyticsEvent,
    WishlistItem, UserProfile ,NegotiationMessage
)

User = get_user_model()


class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "alt_text", "sort_order", "created_at"]
        read_only_fields = ["id", "created_at"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ["id", "name", "parent"]

class ProductSerializer(serializers.ModelSerializer):
    seller = UserPublicSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "created_at", "updated_at",
            "seller", "title", "description", "price", "currency", "condition",
            "is_active", "view_count", "location_city", "location_state", "location_country",
            "category", "min_offer_price", "images"
        ]



class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    # Profile fields
    full_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    address_line1 = serializers.CharField(required=False, allow_blank=True)
    address_line2 = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    state = serializers.CharField(required=False, allow_blank=True)
    country = serializers.CharField(required=False, allow_blank=True)
    pin_code = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "password",
            "full_name", "phone",
            "address_line1", "address_line2",
            "city", "state", "country", "pin_code"
        ]

    def create(self, validated_data):
        profile_fields = {
            key: validated_data.pop(key, "")
            for key in [
                "full_name", "phone", "address_line1", "address_line2",
                "city", "state", "country", "pin_code"
            ]
        }
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)

        # Use get_or_create instead of create
        profile, created = UserProfile.objects.get_or_create(user=user)
        for field, value in profile_fields.items():
            setattr(profile, field, value)
        profile.save()

        return user

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "alt_text", "sort_order"]


class NegotiationMessageSerializer(serializers.ModelSerializer):
    sender = UserPublicSerializer(read_only=True)

    class Meta:
        model = NegotiationMessage
        fields = ["id", "negotiation", "sender", "message", "created_at"]
        read_only_fields = ["id", "sender", "created_at"]



class ProductCreateSerializer(serializers.ModelSerializer):
    images = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )

    class Meta:
        model = Product
        fields = [ "id", "title", "description", "price", "currency", "condition",
                  "is_active", "location_city", "location_state", "location_country",
                  "category", "min_offer_price", "images"]

    def create(self, validated_data):
        images = validated_data.pop("images", [])
        product = Product.objects.create(**validated_data)
        for idx, image in enumerate(images):
            ProductImage.objects.create(
                product=product,
                image=image,
                alt_text=f"Product image {idx+1}",
                sort_order=idx
            )
        return product


class OfferRoundSerializer(serializers.ModelSerializer):
    offered_by = UserPublicSerializer(read_only=True)

    class Meta:
        model = OfferRound
        fields = ["id", "created_at", "offered_by", "price", "message"]


class NegotiationSerializer(serializers.ModelSerializer):
    seller = UserPublicSerializer(read_only=True)
    buyer = UserPublicSerializer(read_only=True)
    rounds = OfferRoundSerializer(many=True, read_only=True)

    class Meta:
        model = Negotiation
        fields = ["id", "created_at", "updated_at", "product", "seller", "buyer", "status", "last_offer_price", "rounds"]
        read_only_fields = ["seller", "buyer", "status", "last_offer_price"]


class DealSerializer(serializers.ModelSerializer):
    buyer = UserPublicSerializer(read_only=True)
    seller = UserPublicSerializer(read_only=True)

    class Meta:
        model = Deal
        fields = ["id", "created_at", "product", "buyer", "seller", "agreed_price", "status"]
        read_only_fields = ["buyer", "seller", "agreed_price"]


class BlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Block
        fields = ["id", "created_at", "blocker", "blocked"]
        read_only_fields = ["blocker"]


class AnalyticsEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyticsEvent
        fields = "__all__"
        read_only_fields = ["user", "ip", "user_agent", "referrer", "country", "region", "city", "lat", "lon"]


class WishlistItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(source="product", queryset=Product.objects.all(), write_only=True)

    class Meta:
        model = WishlistItem
        fields = ["id", "created_at", "product", "product_id"]



class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            "full_name", "phone", "email",
            "address_line1", "address_line2",
            "city", "state", "country", "pin_code",
        ]
