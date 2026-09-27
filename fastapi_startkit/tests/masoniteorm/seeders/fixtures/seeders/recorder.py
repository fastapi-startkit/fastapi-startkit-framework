"""Shared call recorder used by the fixture seeder classes below.

Keeping this as module-level state lets tests assert both that a seeder
ran and the order in which it ran relative to others, without touching a
real database.
"""

CALLS = []
