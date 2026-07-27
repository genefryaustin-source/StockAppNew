"""
Dependency Injection Helpers
"""

from api.services.container import service_container
from api.services.module_registry import ModuleRegistry


def get_module_registry() -> ModuleRegistry:

    return service_container.resolve(
        "modules",
    )