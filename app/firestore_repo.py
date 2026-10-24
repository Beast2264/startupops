"""Firestore implementation of the ``Repository`` interface.

Deliberately behind the SAME interface as ``InMemoryRepository`` so the web
layer and business logic never change. Documents are stored as JSON-mode dumps
of the Pydantic models (dates -> ISO strings, enums -> their values), which
round-trip cleanly through ``model_validate`` on read and are storage-neutral.

Local development and tests point at the Firestore **emulator** via the
FIRESTORE_EMULATOR_HOST environment variable — no real GCP database is
touched. Using this against a real database requires your OWN Google Cloud
project and Application Default Credentials; there is no built-in project.

Security note: models already reject secret-like values; nothing here stores
credentials, tokens, or keys.
"""
from __future__ import annotations

import os
from typing import List, Optional, Type, TypeVar

from google.cloud import firestore

from .models import Application, CreditAward, Followup, Program
from .repository import Repository

M = TypeVar("M", Program, Application, CreditAward, Followup)

COLLECTION_PROGRAMS = "programs"
COLLECTION_APPLICATIONS = "applications"
COLLECTION_CREDITS = "credit_awards"
COLLECTION_FOLLOWUPS = "followups"


def make_client(project: str, database: str = "(default)") -> firestore.Client:
    """Build a Firestore client for YOUR OWN Google Cloud project.

    If FIRESTORE_EMULATOR_HOST is set, the client library automatically routes
    to the emulator with anonymous credentials — so local/test runs never need
    real GCP credentials and never reach a real database. Otherwise this
    requires Application Default Credentials for the given project.
    """
    return firestore.Client(project=project, database=database)


class FirestoreRepository(Repository):
    def __init__(
        self,
        client: Optional[firestore.Client] = None,
        *,
        project: Optional[str] = None,
        database: str = "(default)",
    ) -> None:
        if client is None and not project:
            raise ValueError(
                "FirestoreRepository requires a 'project' (your own Google Cloud "
                "project id) when no client is supplied."
            )
        self._db = client or make_client(project=project, database=database)

    # ------------------------------------------------------------ generic ops
    def _add(self, collection: str, item: M) -> M:
        data = item.model_dump(mode="json")
        if item.id:
            ref = self._db.collection(collection).document(item.id)
        else:
            ref = self._db.collection(collection).document()  # auto id
        data["id"] = ref.id
        ref.set(data)
        return item.model_copy(update={"id": ref.id})

    def _get(self, collection: str, model: Type[M], item_id: str) -> Optional[M]:
        snap = self._db.collection(collection).document(item_id).get()
        if not snap.exists:
            return None
        return model.model_validate(snap.to_dict())

    def _list(self, collection: str, model: Type[M]) -> List[M]:
        return [
            model.model_validate(doc.to_dict())
            for doc in self._db.collection(collection).stream()
        ]

    def _update(self, collection: str, item_id: str, item: M) -> M:
        ref = self._db.collection(collection).document(item_id)
        if not ref.get().exists:
            raise KeyError(item_id)
        data = item.model_dump(mode="json")
        data["id"] = item_id
        ref.set(data)  # full overwrite, mirrors in-memory semantics
        return item.model_copy(update={"id": item_id})

    def _delete(self, collection: str, item_id: str) -> bool:
        ref = self._db.collection(collection).document(item_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True

    # --------------------------------------------------------------- programs
    def list_programs(self) -> List[Program]:
        return self._list(COLLECTION_PROGRAMS, Program)

    def get_program(self, program_id: str) -> Optional[Program]:
        return self._get(COLLECTION_PROGRAMS, Program, program_id)

    def add_program(self, program: Program) -> Program:
        return self._add(COLLECTION_PROGRAMS, program)

    def update_program(self, program_id: str, program: Program) -> Program:
        return self._update(COLLECTION_PROGRAMS, program_id, program)

    def delete_program(self, program_id: str) -> bool:
        return self._delete(COLLECTION_PROGRAMS, program_id)

    # ------------------------------------------------------------ applications
    def list_applications(self) -> List[Application]:
        return self._list(COLLECTION_APPLICATIONS, Application)

    def get_application(self, app_id: str) -> Optional[Application]:
        return self._get(COLLECTION_APPLICATIONS, Application, app_id)

    def add_application(self, app: Application) -> Application:
        return self._add(COLLECTION_APPLICATIONS, app)

    def update_application(self, app_id: str, app: Application) -> Application:
        return self._update(COLLECTION_APPLICATIONS, app_id, app)

    def delete_application(self, app_id: str) -> bool:
        return self._delete(COLLECTION_APPLICATIONS, app_id)

    # ----------------------------------------------------------------- credits
    def list_credits(self) -> List[CreditAward]:
        return self._list(COLLECTION_CREDITS, CreditAward)

    def get_credit(self, credit_id: str) -> Optional[CreditAward]:
        return self._get(COLLECTION_CREDITS, CreditAward, credit_id)

    def add_credit(self, credit: CreditAward) -> CreditAward:
        return self._add(COLLECTION_CREDITS, credit)

    def update_credit(self, credit_id: str, credit: CreditAward) -> CreditAward:
        return self._update(COLLECTION_CREDITS, credit_id, credit)

    def delete_credit(self, credit_id: str) -> bool:
        return self._delete(COLLECTION_CREDITS, credit_id)

    # -------------------------------------------------------------- follow-ups
    def list_followups(self) -> List[Followup]:
        return self._list(COLLECTION_FOLLOWUPS, Followup)

    def get_followup(self, followup_id: str) -> Optional[Followup]:
        return self._get(COLLECTION_FOLLOWUPS, Followup, followup_id)

    def add_followup(self, followup: Followup) -> Followup:
        return self._add(COLLECTION_FOLLOWUPS, followup)

    def update_followup(self, followup_id: str, followup: Followup) -> Followup:
        return self._update(COLLECTION_FOLLOWUPS, followup_id, followup)

    def delete_followup(self, followup_id: str) -> bool:
        return self._delete(COLLECTION_FOLLOWUPS, followup_id)


def emulator_active() -> bool:
    """True when FIRESTORE_EMULATOR_HOST is set (local/test mode)."""
    return bool(os.environ.get("FIRESTORE_EMULATOR_HOST"))
