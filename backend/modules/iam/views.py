from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from core.events import publish
from core.exceptions import DomainError
from core.permissions import Roles, has_role
from modules.registry import facade as registry

from .models import User
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = UserSerializer(request.user).data
        data["facility"] = registry.get_facility(request.user.facility_id) if request.user.facility_id else None
        return Response(data)


class RegisterView(APIView):
    """Self-registration. Licence is checked against the (mocked) practitioner registry; account starts PENDING."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        practitioner = registry.verify_practitioner(data["licence_number"])
        if not practitioner:
            raise DomainError("LICENCE_NOT_FOUND", "Licence number was not found in the practitioner registry.")
        if practitioner["status"] != "ACTIVE":
            raise DomainError("LICENCE_NOT_ACTIVE", "This licence is not active in the practitioner registry.")
        expected = "PHARMACIST" if data["role"] == Roles.PHARMACIST else "PRESCRIBER"
        if practitioner["role_group"] != expected:
            raise DomainError("LICENCE_ROLE_MISMATCH", f"This licence belongs to a {practitioner['cadre']}, not a {data['role'].lower()}.")
        facility = registry.get_facility(data["facility_id"])
        if not facility:
            raise DomainError("FACILITY_NOT_FOUND", "Facility not found.")

        with transaction.atomic():
            user = User.objects.create_user(
                email=data["email"],
                password=data["password"],
                full_name=data["full_name"],
                phone=data.get("phone", ""),
                role=data["role"],
                licence_number=practitioner["licence_number"],
                cadre=practitioner["cadre"],
                facility_id=facility["id"],
                county_code=facility["county_code"],
                status=User.Status.PENDING,
            )
            publish("UserRegistered", {"user_id": user.id, "role": user.role, "facility_id": user.facility_id})
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class UserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [has_role(Roles.SYSTEM_ADMIN, Roles.FACILITY_ADMIN)]

    def get_queryset(self):
        qs = User.objects.all()
        user = self.request.user
        if user.role == Roles.FACILITY_ADMIN:
            qs = qs.filter(facility_id=user.facility_id)
        if s := self.request.query_params.get("status"):
            qs = qs.filter(status=s.upper())
        if f := self.request.query_params.get("facilityId"):
            qs = qs.filter(facility_id=f)
        if r := self.request.query_params.get("role"):
            qs = qs.filter(role=r.upper())
        return qs


class _UserStatusAction(APIView):
    permission_classes = [has_role(Roles.SYSTEM_ADMIN, Roles.FACILITY_ADMIN)]
    new_status = None
    event_name = None

    def post(self, request, user_id):
        target = User.objects.filter(id=user_id).first()
        if not target:
            raise DomainError("USER_NOT_FOUND", "User not found.", status.HTTP_404_NOT_FOUND)
        if request.user.role == Roles.FACILITY_ADMIN and target.facility_id != request.user.facility_id:
            raise DomainError("OUT_OF_SCOPE", "You can only manage users at your own facility.", status.HTTP_403_FORBIDDEN)
        if target.id == request.user.id:
            raise DomainError("SELF_ACTION", "You cannot change your own account status.")
        with transaction.atomic():
            target.status = self.new_status
            if self.new_status == User.Status.ACTIVE:
                target.approved_by = request.user.id
                target.approved_at = timezone.now()
            target.save()
            publish(self.event_name, {"user_id": target.id, "by": request.user.id, "reason": request.data.get("reason", "")})
        return Response(UserSerializer(target).data)


class ApproveUserView(_UserStatusAction):
    new_status = User.Status.ACTIVE
    event_name = "UserApproved"


class SuspendUserView(_UserStatusAction):
    new_status = User.Status.SUSPENDED
    event_name = "UserSuspended"
