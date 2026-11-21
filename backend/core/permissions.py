"""Roles, role checks and the purpose-of-use requirement."""
from rest_framework.permissions import BasePermission


class Roles:
    PRESCRIBER = "PRESCRIBER"
    PHARMACIST = "PHARMACIST"
    FACILITY_ADMIN = "FACILITY_ADMIN"
    REGULATOR = "REGULATOR"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"

    CHOICES = [
        (PRESCRIBER, "Prescriber"),
        (PHARMACIST, "Pharmacist"),
        (FACILITY_ADMIN, "Facility admin"),
        (REGULATOR, "County regulator"),
        (SYSTEM_ADMIN, "System admin"),
    ]
    CLINICAL = (PRESCRIBER, PHARMACIST)


PURPOSES = ("DISPENSING", "PRESCRIBING", "CONSULTATION", "OVERSIGHT", "ADMINISTRATION")
PURPOSE_HEADER = "HTTP_X_PURPOSE_OF_USE"


def has_role(*roles):
    """Permission class factory: has_role(Roles.PHARMACIST, Roles.REGULATOR)."""

    class _HasRole(BasePermission):
        message = f"This action requires one of these roles: {', '.join(roles)}."

        def has_permission(self, request, view):
            user = request.user
            return bool(user and user.is_authenticated and user.role in roles)

    _HasRole.__name__ = f"HasRole_{'_'.join(roles)}"
    return _HasRole


class RequiresPurposeOfUse(BasePermission):
    """Patient-data endpoints must declare why the data is being accessed (X-Purpose-Of-Use)."""

    message = f"Header X-Purpose-Of-Use is required and must be one of: {', '.join(PURPOSES)}."

    def has_permission(self, request, view):
        return request.META.get(PURPOSE_HEADER, "").upper() in PURPOSES


def purpose_of(request):
    return request.META.get(PURPOSE_HEADER, "").upper() or None


def actor_of(request):
    """Plain-dict request context passed into services (no framework objects cross module lines)."""
    user = request.user
    return {
        "id": str(user.id),
        "role": user.role,
        "full_name": user.full_name,
        "licence_number": user.licence_number,
        "facility_id": str(user.facility_id) if user.facility_id else None,
        "county_code": user.county_code,
        "ip": request.META.get("REMOTE_ADDR"),
        "purpose": purpose_of(request),
    }
