from auth.roles import Role, highest_role, role_satisfies


def test_highest_role_picks_admin_over_manager_and_employee():
    assert highest_role(["employee", "manager", "admin"]) == "admin"
    assert highest_role(["employee", "manager"]) == "manager"
    assert highest_role(["employee"]) == "employee"


def test_highest_role_defaults_to_employee_for_empty_or_unknown():
    assert highest_role([]) == "employee"
    assert highest_role(["some-custom-title"]) == "employee"


def test_role_satisfies_hierarchy():
    assert role_satisfies(Role.ADMIN.value, Role.EMPLOYEE.value) is True
    assert role_satisfies(Role.ADMIN.value, Role.MANAGER.value) is True
    assert role_satisfies(Role.MANAGER.value, Role.ADMIN.value) is False
    assert role_satisfies(Role.EMPLOYEE.value, Role.MANAGER.value) is False
    assert role_satisfies(Role.MANAGER.value, Role.MANAGER.value) is True


def test_role_satisfies_treats_none_as_below_employee():
    assert role_satisfies(None, Role.EMPLOYEE.value) is False
