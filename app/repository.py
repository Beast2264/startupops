"""Persistence boundary for StartupOps.

All business logic talks to the ``Repository`` interface, never to a concrete
store. Today the only implementation is ``InMemoryRepository``. A
``FirestoreRepository`` can be added later implementing the same interface —
collections map 1:1 to Firestore collections:

    applications   -> Application
    credit_awards  -> CreditAward
    followups      -> Followup

No business rules live here; this layer only stores and retrieves.
"""
from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from typing import Dict, Generic, List, Optional, TypeVar

from .models import Application, CreditAward, Followup, Program

T = TypeVar("T", Program, Application, CreditAward, Followup)


class Repository(ABC):
    """Abstract persistence interface. Firestore-swappable."""

    # --- programs (catalog) ---
    @abstractmethod
    def list_programs(self) -> List[Program]: ...
    @abstractmethod
    def get_program(self, program_id: str) -> Optional[Program]: ...
    @abstractmethod
    def add_program(self, program: Program) -> Program: ...
    @abstractmethod
    def update_program(self, program_id: str, program: Program) -> Program: ...
    @abstractmethod
    def delete_program(self, program_id: str) -> bool: ...

    # --- applications (submissions) ---
    @abstractmethod
    def list_applications(self) -> List[Application]: ...
    @abstractmethod
    def get_application(self, app_id: str) -> Optional[Application]: ...
    @abstractmethod
    def add_application(self, app: Application) -> Application: ...
    @abstractmethod
    def update_application(self, app_id: str, app: Application) -> Application: ...
    @abstractmethod
    def delete_application(self, app_id: str) -> bool: ...

    # --- credit awards ---
    @abstractmethod
    def list_credits(self) -> List[CreditAward]: ...
    @abstractmethod
    def get_credit(self, credit_id: str) -> Optional[CreditAward]: ...
    @abstractmethod
    def add_credit(self, credit: CreditAward) -> CreditAward: ...
    @abstractmethod
    def update_credit(self, credit_id: str, credit: CreditAward) -> CreditAward: ...
    @abstractmethod
    def delete_credit(self, credit_id: str) -> bool: ...

    # --- follow-ups ---
    @abstractmethod
    def list_followups(self) -> List[Followup]: ...
    @abstractmethod
    def get_followup(self, followup_id: str) -> Optional[Followup]: ...
    @abstractmethod
    def add_followup(self, followup: Followup) -> Followup: ...
    @abstractmethod
    def update_followup(self, followup_id: str, followup: Followup) -> Followup: ...
    @abstractmethod
    def delete_followup(self, followup_id: str) -> bool: ...


class _Collection(Generic[T]):
    """A tiny id-keyed collection used by the in-memory repository."""

    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self._items: Dict[str, T] = {}
        self._counter = itertools.count(1)

    def _next_id(self) -> str:
        return f"{self._prefix}-{next(self._counter):04d}"

    def list(self) -> List[T]:
        return list(self._items.values())

    def get(self, item_id: str) -> Optional[T]:
        return self._items.get(item_id)

    def add(self, item: T) -> T:
        new_id = item.id or self._next_id()
        if new_id in self._items:
            raise ValueError(f"id already exists: {new_id}")
        stored = item.model_copy(update={"id": new_id})
        self._items[new_id] = stored
        return stored

    def update(self, item_id: str, item: T) -> T:
        if item_id not in self._items:
            raise KeyError(item_id)
        stored = item.model_copy(update={"id": item_id})
        self._items[item_id] = stored
        return stored

    def delete(self, item_id: str) -> bool:
        return self._items.pop(item_id, None) is not None


class ReadOnlyError(RuntimeError):
    """Raised when a write is attempted through a read-only repository."""


class ReadOnlyRepository(Repository):
    """Wraps any Repository, allowing reads and refusing all writes.

    Used for LIVE Firestore mode: the UI may read programs/applications/
    credit_awards/followups, but no code path can write to the real database.
    """

    def __init__(self, inner: Repository) -> None:
        self._inner = inner

    @staticmethod
    def _deny(op: str):
        raise ReadOnlyError(
            f"{op} is not permitted: the application is in read-only live mode"
        )

    # reads delegate
    def list_programs(self): return self._inner.list_programs()
    def get_program(self, program_id): return self._inner.get_program(program_id)
    def list_applications(self): return self._inner.list_applications()
    def get_application(self, app_id): return self._inner.get_application(app_id)
    def list_credits(self): return self._inner.list_credits()
    def get_credit(self, credit_id): return self._inner.get_credit(credit_id)
    def list_followups(self): return self._inner.list_followups()
    def get_followup(self, followup_id): return self._inner.get_followup(followup_id)

    # writes are refused
    def add_program(self, program): self._deny("add_program")
    def update_program(self, program_id, program): self._deny("update_program")
    def delete_program(self, program_id): self._deny("delete_program")
    def add_application(self, app): self._deny("add_application")
    def update_application(self, app_id, app): self._deny("update_application")
    def delete_application(self, app_id): self._deny("delete_application")
    def add_credit(self, credit): self._deny("add_credit")
    def update_credit(self, credit_id, credit): self._deny("update_credit")
    def delete_credit(self, credit_id): self._deny("delete_credit")
    def add_followup(self, followup): self._deny("add_followup")
    def update_followup(self, followup_id, followup): self._deny("update_followup")
    def delete_followup(self, followup_id): self._deny("delete_followup")


class InMemoryRepository(Repository):
    """Volatile store — perfect for local dev and tests. No persistence."""

    def __init__(self) -> None:
        self._programs: _Collection[Program] = _Collection("program")
        self._applications: _Collection[Application] = _Collection("app")
        self._credits: _Collection[CreditAward] = _Collection("credit")
        self._followups: _Collection[Followup] = _Collection("followup")

    # programs
    def list_programs(self) -> List[Program]:
        return self._programs.list()

    def get_program(self, program_id: str) -> Optional[Program]:
        return self._programs.get(program_id)

    def add_program(self, program: Program) -> Program:
        return self._programs.add(program)

    def update_program(self, program_id: str, program: Program) -> Program:
        return self._programs.update(program_id, program)

    def delete_program(self, program_id: str) -> bool:
        return self._programs.delete(program_id)

    # applications
    def list_applications(self) -> List[Application]:
        return self._applications.list()

    def get_application(self, app_id: str) -> Optional[Application]:
        return self._applications.get(app_id)

    def add_application(self, app: Application) -> Application:
        return self._applications.add(app)

    def update_application(self, app_id: str, app: Application) -> Application:
        return self._applications.update(app_id, app)

    def delete_application(self, app_id: str) -> bool:
        return self._applications.delete(app_id)

    # credits
    def list_credits(self) -> List[CreditAward]:
        return self._credits.list()

    def get_credit(self, credit_id: str) -> Optional[CreditAward]:
        return self._credits.get(credit_id)

    def add_credit(self, credit: CreditAward) -> CreditAward:
        return self._credits.add(credit)

    def update_credit(self, credit_id: str, credit: CreditAward) -> CreditAward:
        return self._credits.update(credit_id, credit)

    def delete_credit(self, credit_id: str) -> bool:
        return self._credits.delete(credit_id)

    # follow-ups
    def list_followups(self) -> List[Followup]:
        return self._followups.list()

    def get_followup(self, followup_id: str) -> Optional[Followup]:
        return self._followups.get(followup_id)

    def add_followup(self, followup: Followup) -> Followup:
        return self._followups.add(followup)

    def update_followup(self, followup_id: str, followup: Followup) -> Followup:
        return self._followups.update(followup_id, followup)

    def delete_followup(self, followup_id: str) -> bool:
        return self._followups.delete(followup_id)
