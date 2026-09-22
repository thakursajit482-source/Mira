"""Database models package for Mira.

NOTE: In Phase 1 Foundation, this package remains empty.
In subsequent phases, it will contain SQLAlchemy ORM entities:
- User (profile and preferences)
- Roadmap (title, target duration, status, creation date, version metadata)
- Day (roadmap reference, day number, status, ordering)
- Task (day reference, title, description, estimated time, completion status, ordering)
- RoadmapVersion / RoadmapChange (auditable history of changes/insertions)
- AIPlanGeneration (record of AI input/output metadata for debugging and reproducibility)
"""
