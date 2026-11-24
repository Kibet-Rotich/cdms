"""Ports (interfaces) to external systems and their MVP mock implementations."""
from django.conf import settings

from .models import MockRegistryRecord


class ClientRegistryPort:
    def lookup(self, id_type, id_number):
        """Return {cr_id, first_name, middle_name, last_name, date_of_birth, sex, phone} or None."""
        raise NotImplementedError


class PractitionerRegistryPort:
    def lookup(self, licence_number):
        """Return {licence_number, full_name, cadre, regulator, status} or None."""
        raise NotImplementedError


class MockClientRegistry(ClientRegistryPort):
    def lookup(self, id_type, id_number):
        rec = MockRegistryRecord.objects.filter(kind="CLIENT", key=f"{id_type}:{id_number}").first()
        return dict(rec.data) if rec else None


class MockPractitionerRegistry(PractitionerRegistryPort):
    def lookup(self, licence_number):
        rec = MockRegistryRecord.objects.filter(kind="PRACTITIONER", key=licence_number).first()
        return dict(rec.data) if rec else None


def client_registry() -> ClientRegistryPort:
    if settings.INTEROP_MODE == "mock":
        return MockClientRegistry()
    raise NotImplementedError("Live DHA Client Registry adapter is not part of the MVP.")


def practitioner_registry() -> PractitionerRegistryPort:
    if settings.INTEROP_MODE == "mock":
        return MockPractitionerRegistry()
    raise NotImplementedError("Live KMPDC/PPB register adapter is not part of the MVP.")
