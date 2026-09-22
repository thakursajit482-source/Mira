"""AI Integration Layer for Mira.

CORE ARCHITECTURAL RULE:
AI is a scheduling and organization assistant, not an autonomous authority.
- AI accepts user-supplied roadmap content, target duration, and constraints.
- AI analyzes topics, dependencies, and approximate effort.
- AI returns strictly structured JSON data (validated against Pydantic schemas).
- AI NEVER directly accesses or modifies the database.
- AI proposals are passed through validation and the deterministic Roadmap Engine.

NOTE: In Phase 1 Foundation, this package defines the architectural boundary.
LLM client integration begins in subsequent phases.
"""
