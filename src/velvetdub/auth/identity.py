"""Who is making this request?

The API depends on `IdentityProvider`, never on a concrete user. Today it is always the local
user. To add accounts later, write a provider that reads a session or token and register it in
the container. Routes, services and storage already take an owner id, so nothing else changes.
"""

from abc import ABC, abstractmethod

from starlette.requests import Request

from velvetdub.domain.user import LOCAL_USER, User


class IdentityProvider(ABC):
    @abstractmethod
    def current_user(self, request: Request) -> User: ...


class LocalIdentityProvider(IdentityProvider):
    """Single-user mode: everyone is the local user."""

    def current_user(self, request: Request) -> User:
        return LOCAL_USER
