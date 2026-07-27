"""
Application Service Registry
"""

from api.services.container import service_container
from api.services.module_registry import module_registry, ModuleRegistry


def register_services() -> None:
    """
    Register application-wide services.
    """

    service_container.register(
        "modules",
        module_registry,
    )

module_registry = ModuleRegistry()


def get_module_registry() -> ModuleRegistry:
    return module_registry