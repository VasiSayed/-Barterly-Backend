from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductViewSet, ProductImageViewSet, CategoryViewSet,
    NegotiationViewSet, DealViewSet, BlockViewSet,
    WishlistViewSet, AnalyticsViewSet, MeProfileViewSet,RegisterView
)

router = DefaultRouter()
router.register(r"products", ProductViewSet, basename="product")
router.register(r"product-images", ProductImageViewSet, basename="product-image")
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"negotiations", NegotiationViewSet, basename="negotiation")
router.register(r"deals", DealViewSet, basename="deal")
router.register(r"blocks", BlockViewSet, basename="block")
router.register(r"wishlist", WishlistViewSet, basename="wishlist")

urlpatterns = [
    path("", include(router.urls)),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("analytics/top-products/", AnalyticsViewSet.as_view({"get": "top_products"}), name="analytics-top-products"),
    path("analytics/by-location/",   AnalyticsViewSet.as_view({"get": "by_location"}),   name="analytics-by-location"),
    path("me/profile/get/",          MeProfileViewSet.as_view({"get": "get"}),           name="me-profile-get"),
    path("me/profile/update/",       MeProfileViewSet.as_view({"put": "update", "patch": "update"}), name="me-profile-update"),
]
