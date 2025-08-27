from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        owner = getattr(obj, "seller", None) or getattr(obj, "owner", None) or getattr(obj, "user", None)
        return owner and owner == request.user
