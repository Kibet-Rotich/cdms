"""Public interface of the IAM module. Other modules import only from here."""
from .models import User


def _dto(user):
    return {
        "id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "licence_number": user.licence_number,
        "facility_id": str(user.facility_id) if user.facility_id else None,
        "county_code": user.county_code,
        "status": user.status,
    }


def get_user(user_id):
    user = User.objects.filter(id=user_id).first()
    return _dto(user) if user else None


def get_users_map(user_ids):
    return {str(u.id): _dto(u) for u in User.objects.filter(id__in=list(user_ids))}
