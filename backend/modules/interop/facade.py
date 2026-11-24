"""Public interface of the Interop module: access to external national systems."""
from . import adapters


def lookup_client(id_type, id_number):
    return adapters.client_registry().lookup(id_type, id_number)


def lookup_practitioner(licence_number):
    return adapters.practitioner_registry().lookup(licence_number)
