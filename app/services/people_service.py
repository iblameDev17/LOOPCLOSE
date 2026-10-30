"""People service: manages person creation, retrieval, and listing."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import NotFoundError, ValidationFailed
from app.logging_config import log_event
from app.models.person import Person
from app.schemas.person import PersonCreate

logger = logging.getLogger("app.meetings")


def list_people(db: Session, active_only: bool = False) -> list[Person]:
    """Return all people, optionally filtered to active people only."""
    stmt = select(Person)
    if active_only:
        stmt = stmt.where(Person.is_active.is_(True))
    stmt = stmt.order_by(Person.name.asc())
    return list(db.scalars(stmt).all())


def get_person(db: Session, person_id: int) -> Person:
    """Get a person by ID or raise NotFoundError."""
    person = db.get(Person, person_id)
    if not person:
        raise NotFoundError(f"Person with id {person_id} not found.")
    return person


def create_person(db: Session, data: PersonCreate) -> Person:
    """Create a new person after checking email uniqueness."""
    name = data.name.strip()
    if not name:
        raise ValidationFailed("Name is required.", field="name")

    if data.email:
        existing = db.scalar(select(Person).where(Person.email == data.email))
        if existing:
            raise ValidationFailed("That email is already used.", field="email")

    person = Person(
        name=name,
        email=data.email,
        role_title=data.role_title.strip() if data.role_title else None,
        is_active=data.is_active,
    )
    db.add(person)
    db.commit()
    db.refresh(person)

    log_event(
        logger,
        "person.created",
        person_id=person.id,
        name=person.name,
        is_active=person.is_active,
    )
    return person
