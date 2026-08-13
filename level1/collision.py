"""Collision helpers kept independent from game-state mutation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, TypeVar

import pygame


class HasRect(Protocol):
    @property
    def rect(self) -> pygame.Rect: ...


T = TypeVar("T", bound=HasRect)


def first_collision(rect: pygame.Rect, objects: Iterable[T]) -> T | None:
    """Return the first object whose rectangle intersects ``rect``."""
    for obj in objects:
        if rect.colliderect(obj.rect):
            return obj
    return None


def all_collisions(rect: pygame.Rect, objects: Iterable[T]) -> list[T]:
    return [obj for obj in objects if rect.colliderect(obj.rect)]

