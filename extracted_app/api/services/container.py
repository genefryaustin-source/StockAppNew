"""
Service Container

Central registry for application services.

The container owns singleton instances that are reused
throughout the FastAPI application.
"""

from __future__ import annotations

from typing import Any


class ServiceContainer:

    def __init__(self) -> None:

        self._services: dict[str, Any] = {}

    def register(
        self,
        name: str,
        service: Any,
    ) -> None:

        self._services[name] = service

    def resolve(
        self,
        name: str,
    ) -> Any:

        if name not in self._services:
            raise KeyError(
                f"Service '{name}' has not been registered."
            )

        return self._services[name]

    def registered_services(self) -> list[str]:

        return sorted(self._services.keys())

    def contains(
        self,
        name: str,
    ) -> bool:

        return name in self._services


service_container = ServiceContainer()