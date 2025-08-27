from decimal import Decimal
from django.db import transaction
from django.db.models import Count, Q
from django.contrib.auth import get_user_model
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import serializers, status
from django.db.models import Q, Count, Case, When, IntegerField,Sum

from .models import (
    Product, ProductImage, ProductCategory,
    Negotiation, OfferRound, Deal, Block, AnalyticsEvent,
    WishlistItem, UserProfile
)
from rest_framework import generics, permissions

from .serializers import (

    ProductSerializer, ProductCreateSerializer, ProductImageSerializer, CategorySerializer,
    NegotiationSerializer, OfferRoundSerializer, DealSerializer, BlockSerializer,
    AnalyticsEventSerializer, WishlistItemSerializer, UserProfileSerializer,UserRegisterSerializer
)
from .permissions import IsOwnerOrReadOnly
from .utils import record_event


User = get_user_model()



class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related("seller", "category")
    filterset_fields = ["condition", "currency", "location_city", "location_state", "location_country", "seller", "category"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "price", "view_count"]

    def get_queryset(self):
        if self.action == "list":
            qs = Product.objects.filter(is_active=True)
            if self.request.user.is_authenticated:
                qs = qs.exclude(seller=self.request.user)
            return qs.select_related("seller", "category")
        return Product.objects.all().select_related("seller", "category")

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return ProductCreateSerializer
        return ProductSerializer

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        record_event(request, event_type=AnalyticsEvent.Type.PRODUCT_VIEW, product=instance)
        return super().retrieve(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()

        if request.user.is_authenticated:
            qs = qs.exclude(seller=request.user)

        qs = self.filter_queryset(
            qs.annotate(
                product_view_count=Count(
                    "analyticsevent",
                    filter=Q(analyticsevent__event_type=AnalyticsEvent.Type.PRODUCT_VIEW)
                )
            )
        )

        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True, context={"request": request})

        products_data = serializer.data
        for i, prod in enumerate(page or qs):
            products_data[i]["product_view_count"] = prod.product_view_count

        response_data = {"products": products_data}

        if request.user.is_authenticated:
            last_view_event = (
                AnalyticsEvent.objects.filter(user=request.user, event_type=AnalyticsEvent.Type.PRODUCT_VIEW)
                .order_by("-created_at")
                .select_related("product")
                .first()
            )
            if last_view_event and last_view_event.product:
                response_data["last_viewed_product"] = ProductSerializer(
                    last_view_event.product, context={"request": request}
                ).data

            # Categories seen by this user
            categories_seen = (
                AnalyticsEvent.objects.filter(
                    user=request.user,
                    event_type=AnalyticsEvent.Type.PRODUCT_VIEW,
                    product__category__isnull=False
                )
                .values("product__category__id", "product__category__name")
                .distinct()
            )
            response_data["categories_seen"] = list(categories_seen)

        if page is not None:
            return self.get_paginated_response(response_data)
        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def click(self, request, pk=None):
        product = self.get_object()
        record_event(request, event_type=AnalyticsEvent.Type.PRODUCT_CLICK, product=product)
        return Response({"ok": True})

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def mine(self, request):
        qs = Product.objects.filter(seller=request.user).annotate(
            product_view_count=Count(
                "analyticsevent",
                filter=Q(analyticsevent__event_type=AnalyticsEvent.Type.PRODUCT_VIEW)
            ),
            product_click_count=Count(
                "analyticsevent",
                filter=Q(analyticsevent__event_type=AnalyticsEvent.Type.PRODUCT_CLICK)
            ),
            wishlist_count=Count("wishlisted_by", distinct=True)
        )

        page = self.paginate_queryset(qs)
        serializer = ProductSerializer(page or qs, many=True, context={"request": request})
        products_data = serializer.data

        for i, prod in enumerate(page or qs):
            products_data[i]["product_view_count"] = prod.product_view_count
            products_data[i]["product_click_count"] = prod.product_click_count
            products_data[i]["wishlist_count"] = prod.wishlist_count

        total_analytics = qs.aggregate(
            total_views=Sum("product_view_count"),
            total_clicks=Sum("product_click_count"),
            total_wishlists=Sum("wishlist_count")
        )

        response_data = {
            "products": products_data,
            "totals": total_analytics
        }

        if page is not None:
            # DRF pagination wrapper
            return self.get_paginated_response(response_data)

        return Response(response_data, status=status.HTTP_200_OK)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]


class ProductImageViewSet(viewsets.ModelViewSet):
    queryset = ProductImage.objects.select_related("product")
    serializer_class = ProductImageSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs = super().get_queryset()
        product_id = self.request.query_params.get("product")
        if product_id:
            qs = qs.filter(product_id=product_id)
        return qs

    def perform_create(self, serializer):
        product_id = self.request.data.get("product")
        if not product_id:
            raise serializers.ValidationError({"product": "required"})
        try:
            product = Product.objects.get(id=product_id, seller=self.request.user)
        except Product.DoesNotExist:
            raise serializers.ValidationError({"product": "not found or not owner"})
        serializer.save(product=product)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        if not self.request.user.is_staff:
            raise serializers.ValidationError({"detail": "Only staff can create categories"})
        serializer.save()


class NegotiationViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = Negotiation.objects.select_related("product", "seller", "buyer")
    serializer_class = NegotiationSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset().filter(Q(seller=request.user) | Q(buyer=request.user))
        qs = qs.order_by(
            Case(
                When(status=Negotiation.Status.OPEN, then=0),
                default=1,
                output_field=IntegerField(),
            ),
            "-updated_at"
        )
        return self._paginate(qs)

    from collections import OrderedDict

    @action(detail=False, methods=["get"])
    def selling(self, request):
        qs = self.get_queryset().filter(seller=request.user).order_by(
            Case(
                When(status=Negotiation.Status.OPEN, then=0),
                default=1,
                output_field=IntegerField(),
            ),
            "-updated_at"
        )
        page = self.paginate_queryset(qs)
        buying_count = Negotiation.objects.filter(buyer=request.user).count()

        if page is not None:
            ser = self.get_serializer(page, many=True)
            response = self.get_paginated_response(ser.data)
            response.data.update({"buying_count": buying_count})
            return response

        ser = self.get_serializer(qs, many=True)
        return Response({"results": ser.data, "buying_count": buying_count})


    @action(detail=False, methods=["get"])
    def buying(self, request):
        qs = self.get_queryset().filter(buyer=request.user).order_by(
            Case(
                When(status=Negotiation.Status.OPEN, then=0),
                default=1,
                output_field=IntegerField(),
            ),
            "-updated_at"
        )
        page = self.paginate_queryset(qs)
        selling_count = Negotiation.objects.filter(seller=request.user).count()

        if page is not None:
            ser = self.get_serializer(page, many=True)
            response = self.get_paginated_response(ser.data)
            response.data.update({"selling_count": selling_count})
            return response

        ser = self.get_serializer(qs, many=True)
        return Response({"results": ser.data, "selling_count": selling_count})


    def _paginate(self, qs):
        page = self.paginate_queryset(qs)
        if page is not None:
            ser = self.get_serializer(page, many=True)
            return self.get_paginated_response(ser.data)
        return Response(self.get_serializer(qs, many=True).data)


    def _validate_min_offer(self, product: Product, price: Decimal):
        return not (product.min_offer_price and Decimal(price) < product.min_offer_price)

    @action(detail=False, methods=["post"])
    def start(self, request):
        product_id = request.data.get("product")
        price = request.data.get("price")
        message = request.data.get("message", "")

        if not product_id or price is None:
            return Response({"detail": "product and price required"}, status=400)

        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({"detail": "Product not found"}, status=404)

        if product.seller == request.user:
            return Response({"detail": "You can't negotiate on your own product."}, status=400)

        if not self._validate_min_offer(product, Decimal(price)):
            return Response({"detail": f"Minimum offer is {product.min_offer_price}"}, status=400)

        if Block.objects.filter(blocker=product.seller, blocked=request.user).exists() or \
        Block.objects.filter(blocker=request.user, blocked=product.seller).exists():
            return Response({"detail": "You cannot negotiate with this user."}, status=403)

        with transaction.atomic():
            existing = Negotiation.objects.filter(
                product=product, seller=product.seller, buyer=request.user, status=Negotiation.Status.OPEN
            ).first()

            if existing:
                existing.status = Negotiation.Status.CANCELED
                existing.save(update_fields=["status", "updated_at"])

            # ✅ create new negotiation
            neg = Negotiation.objects.create(
                product=product,
                seller=product.seller,
                buyer=request.user,
                last_offer_price=Decimal(price),
            )
            OfferRound.objects.create(
                negotiation=neg,
                offered_by=request.user,
                price=Decimal(price),
                message=message
            )

        record_event(
            request,
            event_type=AnalyticsEvent.Type.OFFER_CREATED,
            product=product,
            negotiation=neg,
            extra={"role": "buyer"}
        )
        return Response(NegotiationSerializer(neg).data, status=201)

    @action(detail=True, methods=["post"])
    def offer(self, request, pk=None):
        neg = self.get_object()
        if neg.status != Negotiation.Status.OPEN:
            return Response({"detail": "Negotiation is not open."}, status=400)
        if not neg.is_party(request.user):
            return Response({"detail": "Not a party to this negotiation."}, status=403)
        price = request.data.get("price")
        message = request.data.get("message", "")
        if price is None:
            return Response({"detail": "price required"}, status=400)
        if not self._validate_min_offer(neg.product, Decimal(price)):
            return Response({"detail": f"Minimum offer is {neg.product.min_offer_price}"}, status=400)
        OfferRound.objects.create(negotiation=neg, offered_by=request.user, price=Decimal(price), message=message)
        neg.last_offer_price = Decimal(price)
        neg.save(update_fields=["last_offer_price", "updated_at"])
        record_event(request, event_type=AnalyticsEvent.Type.OFFER_CREATED, product=neg.product, negotiation=neg)
        return Response(NegotiationSerializer(neg).data)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        neg = self.get_object()
        if neg.status != Negotiation.Status.OPEN:
            return Response({"detail": "Negotiation not open."}, status=400)
        last_round = neg.rounds.order_by("-created_at").first()
        if not last_round:
            return Response({"detail": "No offers to accept."}, status=400)
        if last_round.offered_by == request.user:
            return Response({"detail": "Counter-party must accept."}, status=400)
        with transaction.atomic():
            neg.status = Negotiation.Status.ACCEPTED
            neg.save(update_fields=["status", "updated_at"])
            deal = Deal.objects.create(
                product=neg.product,
                buyer=neg.buyer,
                seller=neg.seller,
                agreed_price=neg.last_offer_price,
            )
        record_event(request, event_type=AnalyticsEvent.Type.OFFER_ACCEPTED, product=neg.product, negotiation=neg)

        # attach contact details of both parties
        def pack(u):
            prof = getattr(u, "profile", None)
            return UserProfileSerializer(prof).data if prof else {
                "full_name": getattr(u, "get_full_name", lambda: u.username)(),
                "email": getattr(u, "email", ""),
                "phone": "",
                "address_line1": "", "address_line2": "",
                "city": "", "state": "", "country": "", "pin_code": "",
            }

        data = {
            "negotiation": NegotiationSerializer(neg).data,
            "deal": DealSerializer(deal).data,
            "buyer_contact": pack(neg.buyer),
            "seller_contact": pack(neg.seller),
        }
        return Response(data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        neg = self.get_object()
        if not neg.is_party(request.user):
            return Response({"detail": "Not a party to this negotiation."}, status=403)
        if neg.status != Negotiation.Status.OPEN:
            return Response({"detail": "Negotiation not open."}, status=400)
        neg.status = Negotiation.Status.REJECTED
        neg.save(update_fields=["status", "updated_at"])
        return Response(NegotiationSerializer(neg).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        neg = self.get_object()
        if request.user not in [neg.buyer, neg.seller]:
            return Response({"detail": "Not a party to this negotiation."}, status=403)
        neg.status = Negotiation.Status.CANCELED
        neg.save(update_fields=["status", "updated_at"])
        return Response(NegotiationSerializer(neg).data)


class DealViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DealSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Deal.objects.filter(Q(buyer=self.request.user) | Q(seller=self.request.user)) \
                         .select_related("product", "buyer", "seller")
        return qs.order_by(
            Case(
                When(status=Deal.Status.PENDING, then=0),
                default=1,
                output_field=IntegerField(),
            ),
            "-updated_at"
        )

    @action(detail=False, methods=["get"])
    def sales(self, request):
        qs = Deal.objects.filter(seller=request.user).select_related("product", "buyer", "seller") \
                        .order_by(
                            Case(
                                When(status=Deal.Status.PENDING, then=0),
                                default=1,
                                output_field=IntegerField(),
                            ),
                            "-updated_at"
                        )
        page = self.paginate_queryset(qs)
        purchases_count = Deal.objects.filter(buyer=request.user).count()

        if page is not None:
            ser = DealSerializer(page, many=True)
            response = self.get_paginated_response(ser.data)
            response.data.update({"purchases_count": purchases_count})
            return response

        ser = DealSerializer(qs, many=True)
        return Response({"results": ser.data, "purchases_count": purchases_count})


    @action(detail=False, methods=["get"])
    def purchases(self, request):
        qs = Deal.objects.filter(buyer=request.user).select_related("product", "buyer", "seller") \
                        .order_by(
                            Case(
                                When(status=Deal.Status.PENDING, then=0),
                                default=1,
                                output_field=IntegerField(),
                            ),
                            "-updated_at"
                        )
        page = self.paginate_queryset(qs)
        sales_count = Deal.objects.filter(seller=request.user).count()

        if page is not None:
            ser = DealSerializer(page, many=True)
            response = self.get_paginated_response(ser.data)
            response.data.update({"sales_count": sales_count})
            return response

        ser = DealSerializer(qs, many=True)
        return Response({"results": ser.data, "sales_count": sales_count})

    @action(detail=True, methods=["patch"], url_path="update-status")
    def update_status(self, request, pk=None):
        deal = self.get_object()

        if request.user not in [ deal.seller]:
            return Response(
                {"detail": "You are not authorized to update this deal."},
                status=status.HTTP_403_FORBIDDEN,
            )

        new_status = request.data.get("status")
        if not new_status:
            return Response({"detail": "status is required"}, status=status.HTTP_400_BAD_REQUEST)

        if new_status not in Deal.Status.values:
            return Response(
                {"detail": f"Invalid status. Must be one of {Deal.Status.values}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deal.status = new_status
        deal.save(update_fields=["status", "updated_at"])
        return Response(DealSerializer(deal).data, status=status.HTTP_200_OK)


class BlockViewSet(viewsets.ModelViewSet):
    serializer_class = BlockSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Block.objects.filter(blocker=self.request.user)

    def perform_create(self, serializer):
        serializer.save(blocker=self.request.user)


class WishlistViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WishlistItem.objects.filter(user=self.request.user).select_related("product")

    def perform_create(self, serializer):
        item = serializer.save(user=self.request.user)
        record_event(self.request, event_type=AnalyticsEvent.Type.WISHLIST_ADD, product=item.product)

    @action(detail=True, methods=["delete"])
    def remove(self, request, pk=None):
        try:
            item = WishlistItem.objects.get(user=request.user, product_id=pk)
            item.delete()
            return Response({"detail": "Removed from wishlist"}, status=status.HTTP_204_NO_CONTENT)
        except WishlistItem.DoesNotExist:
            return Response({"detail": "Not in wishlist"}, status=status.HTTP_404_NOT_FOUND)


class AnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def top_products(self, request):
        type_ = request.query_params.get("type", AnalyticsEvent.Type.PRODUCT_VIEW)
        qs = AnalyticsEvent.objects.filter(event_type=type_, product__isnull=False)
        agg = qs.values("product").annotate(count=Count("id")).order_by("-count")[:20]
        product_ids = [a["product"] for a in agg]
        prods = {str(p.id): p for p in Product.objects.filter(id__in=product_ids)}
        data = [
            {"product_id": a["product"], "count": a["count"], "title": getattr(prods.get(str(a["product"])), "title", None)}
            for a in agg
        ]
        return Response(data)

    @action(detail=False, methods=["get"])
    def by_location(self, request):
        type_ = request.query_params.get("type", AnalyticsEvent.Type.PRODUCT_VIEW)
        qs = AnalyticsEvent.objects.filter(event_type=type_)
        agg = qs.values("country", "region", "city").annotate(count=Count("id")).order_by("-count")[:100]
        return Response(list(agg))


class MeProfileViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def get(self, request):
        prof, _ = UserProfile.objects.get_or_create(user=request.user, defaults={"email": request.user.email})
        return Response(UserProfileSerializer(prof).data)

    @action(detail=False, methods=["put", "patch"])
    def update(self, request):
        prof, _ = UserProfile.objects.get_or_create(user=request.user, defaults={"email": request.user.email})
        ser = UserProfileSerializer(prof, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)
