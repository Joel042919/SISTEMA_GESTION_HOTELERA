from typing import Set


# Mínimo mapa en memoria; en producción, consultar a BD
ROLE_PERMS = {
    "Administrador": {"*"},
    "Recepcion": {"reservations.create","reservations.view","reservations.list","reservations.update","reservations.cancel","reservations.assign_room","billing.view","billing.pay","rooms.view"},
    "Housekeeping": {"rooms.update_status","rooms.view"},
    "Finanzas": {"billing.view","billing.charge","billing.pay","billing.close_cash","reports.view"},
    "Gerencia": {"reports.view","reservations.view","reservations.list"}
}


def is_allowed(user_roles: list[str], perm: str) -> bool:
    for r in user_roles:
        perms: Set[str] = ROLE_PERMS.get(r, set())
        if "*" in perms or perm in perms:
            return True
    return False