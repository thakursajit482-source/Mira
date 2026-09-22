# Personal AI Roadmap System (Mira)
## Product Requirements Document (PRD)
**Version 1.0 | MVP | Personal Use**

---

## 1. Product Overview
The Personal AI Roadmap System is a web application designed to solve a personal execution problem: creating a roadmap is easy, but consistently following and completing it is difficult. The system does not primarily create learning plans from scratch. Instead, the user provides a roadmap or plan they trust, and the AI converts, schedules, inserts, and reschedules that content into an executable day-wise roadmap.

The product combines AI-assisted scheduling with a game-like roadmap experience. Each day behaves like a level, and each day can contain multiple tasks. The user completes individual tasks, and a day becomes complete only when all tasks assigned to that day are completed.

---

## 2. Product Philosophy
* The user owns the roadmap and decides what content should be learned or completed.
* AI is a scheduling and organization engine, not the authority that decides the user's long-term learning goals.
* Completed history must be protected from accidental AI changes.
* New content should be inserted at the user's current incomplete point rather than simply appended to the end.
* The original roadmap's total duration/deadline should remain fixed unless the user explicitly chooses to change it.
* The interface should make progress feel like progressing through game levels without becoming cluttered.

---

## 3. Problem Statement
The user frequently creates or receives useful roadmaps but fails to complete them consistently. Plans may also change because new assignments, subjects, skills, projects, or time constraints appear. Manually reorganizing a long roadmap every time this happens is inconvenient and makes the user abandon the plan.

The application should therefore turn a static roadmap into a living execution system that can adapt while preserving completed progress and the overall target duration.

---

## 4. Goals
* Convert a supplied roadmap into a practical day-wise schedule.
* Allow multiple tasks on a single day.
* Track completion at the individual-task level.
* Represent each day as a visual level in a game-like roadmap.
* Insert new roadmap content starting from the first incomplete day.
* Shift future old tasks when new content is inserted.
* Preserve completed days and completed tasks.
* Preserve the original total roadmap duration when inserting new content.
* Allow future workload to be rebalanced when necessary.
* Provide a simple personal dashboard rather than a large social/productivity platform.

---

## 5. Non-Goals for MVP
* No public marketplace or social network.
* No multi-user collaboration.
* No requirement for the AI to invent the user's entire learning strategy.
* No automatic modification of completed days.
* No mobile application in MVP; the first version is a web application.
* No excessive gamification, leaderboards, avatars, or social competition.
* No unnecessary enterprise productivity features.

---

## 6. Target User
Primary target: the creator of this project, initially using the system as a personal execution tool. The architecture should not prevent future multi-user support, but MVP decisions should prioritize simplicity and speed.

---

## 7. Core User Flow
```
AI Page
  ↓
Paste roadmap/content + duration + available time
  ↓
AI analyzes and produces structured day-wise tasks
  ↓
User reviews/accepts the generated roadmap
  ↓
Roadmap Page
  ↓
Open current day
  ↓
Complete individual tasks
  ↓
All tasks complete → Day complete → Next level becomes available
```

---

## 8. Application Structure

### 8.1 AI Page
* Primary input area for an original roadmap or a new roadmap/content block.
* Duration input: number of days allocated to the supplied content.
* Optional daily available time input.
* Action for generating an initial roadmap.
* Action for adding/inserting new roadmap content into the active roadmap.
* Preview of the resulting schedule before committing changes.
* Clear indication of what will be inserted and which future days will shift.

### 8.2 Roadmap Page
* Primary execution screen.
* Vertical/game-like sequence of day levels.
* Completed days visually distinct from current and locked future days.
* Current/incomplete day clearly highlighted.
* Each day displays its task count and progress.
* Clicking a day opens its task list.
* Individual tasks can be marked complete.
* Day becomes complete only when all assigned tasks are complete.
* Overall progress is shown as completed days / total days.
* Optional streak/XP/achievement layer can be added after core execution works.

### 8.3 Profile / Settings
* Basic user profile.
* Active roadmap information.
* Target duration/deadline.
* Daily available time.
* Preferences.
* Roadmap archive/reset controls.
* Notification settings may be added later.

---

## 9. Roadmap Data Model
Conceptual hierarchy:
```
User
└── Active Roadmap
    ├── Day 1
    │   ├── Task 1
    │   ├── Task 2
    │   └── Task 3
    ├── Day 2
    │   ├── Task 1
    │   └── Task 2
    └── Day N
        └── Tasks...
```
* A day is a container, not a single task.
* A task is the smallest completion unit.
* Tasks should have an order within a day.
* Tasks should support completion state.
* Tasks may include title, description, estimated time, source/category, and order.

---

## 10. Initial Roadmap Generation
When creating a new active roadmap, the user supplies trusted roadmap content and a target duration. The AI analyzes the content and distributes tasks logically across the requested number of days.
* The AI must not blindly split text into equal-sized chunks.
* Dependencies and logical order should be respected.
* Multiple tasks may be assigned to the same day.
* The AI may use estimated task effort and the user's available daily time to balance workload.
* The generated roadmap should be returned in structured machine-readable data, not only prose.
* The backend must validate the AI response before saving it.

---

## 11. New Roadmap Insertion Rule — CORE PRODUCT RULE
When the user provides a new roadmap/content block while an active roadmap already exists, the system must insert the new content starting from the first incomplete day.

**Example:**
* Existing roadmap = 40 days
* Completed = Day 1, Day 2, Day 3
* First incomplete day = Day 4
* New roadmap duration = 3 days

**Result:**
* Day 1–3 → unchanged and locked as completed history
* Day 4–6 → new roadmap content
* Day 7+ → original future roadmap content shifted forward
* Overall roadmap duration → remains 40 days

**Core Insertion Invariants:**
* The new roadmap is NOT appended to Day 41.
* Completed days must never be overwritten.
* Existing future tasks are shifted, not deleted, where possible.
* The new content occupies the requested number of day slots.
* The total roadmap duration remains fixed.
* The system must rebalance future tasks if inserting the new content creates a scheduling conflict.
* If the requested insertion cannot fit while preserving the fixed deadline, the system must explain the conflict and request user confirmation or offer a rebalance preview rather than silently extending the roadmap.

---

## 12. Partial-Day / Incomplete Task Rule
A day may contain several tasks. Individual tasks have independent completion states.
```
DAY 1
✓ Python Basics
✓ AOA Assignment 1
○ COA Experiment 6

Day status = In Progress / Incomplete
```
* A day is completed only when every required task assigned to that day is completed.
* The first incomplete day is determined from the roadmap's actual task/day completion state.
* New roadmap insertion begins from that current incomplete point.
* If a previous day contains unfinished tasks, those tasks remain visible and are not silently deleted.

---

## 13. Fixed Duration and Rebalancing
The roadmap has a target duration. Adding new content does not automatically extend that duration.
* Example: 40-day roadmap remains a 40-day roadmap after inserting a 3-day new roadmap.
* Future original tasks may shift forward and be redistributed across remaining days.
* The system should prioritize preserving logical task order and dependencies.
* The system should avoid unrealistic daily workloads.
* If the user changes available daily time, only future/incomplete work should be rescheduled; completed history remains unchanged.
* Any major schedule change should be previewable before confirmation.

---

## 14. AI Responsibilities
* Understand supplied roadmap content.
* Identify tasks, topics, dependencies, and approximate effort.
* Distribute content across the requested duration.
* Merge new content into the active roadmap from the current incomplete point.
* Suggest future workload rebalancing when required.
* Return structured data that the backend can validate.
* Explain scheduling conflicts in human-readable language.

**AI must NOT:**
* Modify completed history without explicit user action.
* Invent unrelated roadmap content merely to fill days.
* Automatically extend the roadmap beyond its target duration when the user requested a fixed duration.
* Delete future tasks without preserving or explicitly showing the change.

---

## 15. Roadmap Engine Responsibilities
The roadmap engine is deterministic application logic and should remain separate from the AI. The AI proposes structured scheduling; the roadmap engine applies and validates product rules.
* Find first incomplete day.
* Lock completed days.
* Insert new day/task groups.
* Shift future tasks.
* Preserve total duration.
* Recalculate day numbering/order.
* Rebalance future workload where needed.
* Maintain task completion states.
* Create an auditable change history for roadmap modifications.

---

## 16. Example: Full Insertion Scenario
**BEFORE**
```
Day 1 ✓
Day 2 ✓
Day 3 ✓
Day 4 Original Topic A
Day 5 Original Topic B
Day 6 Original Topic C
...
Day 40 Original Topic Z
```

**USER INPUT**
* New roadmap: Git & GitHub
* Duration: 3 days

**AFTER**
```
Day 1 ✓ Original
Day 2 ✓ Original
Day 3 ✓ Original
Day 4 New: Git Basics
Day 5 New: Git Commands
Day 6 New: GitHub/Branching
Day 7 Original Topic A
Day 8 Original Topic B
Day 9 Original Topic C
...
Day 40 Remaining original work after rebalance
```
*The exact final distribution may change because the system must fit the shifted original work back into the remaining fixed-duration schedule.*

---

## 17. Progress States
* **Locked** — future day that is not yet available.
* **Current** — first day requiring action.
* **In Progress** — one or more tasks completed, but not all.
* **Completed** — all required tasks are complete.
* **At Risk / Overdue** — optional future state for deadline tracking.
* **Skipped** — optional future state; should require explicit user action.

---

## 18. Gamification / UX Direction
* Day nodes should visually resemble game levels.
* Completed levels should provide a satisfying visual state change.
* Current level should be visually prominent.
* Future levels should appear locked but visible enough to motivate progress.
* Animations should be micro-interactions, not distracting effects.
* Optional XP, streaks, achievements, and completion animations should be layered on top of working task logic.
* The interface should remain clean and readable.

---

## 19. Suggested Technical Architecture
```
Web Client
    ↓
Application Backend / API
    ├── Authentication
    ├── Roadmap Service
    ├── Task/Progress Service
    ├── AI Service
    └── Roadmap Engine
    ↓
PostgreSQL Database
```

---

## 20. Conceptual Database Entities
* **User** — profile and preferences.
* **Roadmap** — title, target duration, status, creation date, version/history metadata.
* **Day** — roadmap reference, day number, status, ordering.
* **Task** — day reference, title, description, estimated time, completion status, ordering.
* **RoadmapChange / RoadmapVersion** — records insertions, rescheduling, or major updates.
* **AIPlanGeneration** — optional record of AI input/output metadata for debugging and reproducibility.

---

## 21. Important API/Service Operations
* Create roadmap from supplied content.
* Get active roadmap.
* Get roadmap day.
* Complete/uncomplete task.
* Calculate day status.
* Insert new roadmap.
* Preview roadmap insertion.
* Confirm roadmap insertion.
* Reschedule remaining roadmap.
* Update daily available time.
* Get progress statistics.

---

## 22. Safety and Data Integrity Rules
* Completed task state must not be overwritten by an AI scheduling operation.
* Roadmap mutations should be transactional where possible.
* Insertion should have a preview/confirmation step before destructive or large changes.
* The system should retain a previous roadmap version or change history so changes can be reversed.
* AI output must be validated against schema before database mutation.
* The client should not be trusted to enforce completion or roadmap rules; the backend must enforce them.

---

## 23. MVP Scope
* Single active roadmap.
* AI Page.
* Roadmap Page.
* Profile/Settings Page.
* Initial roadmap generation.
* Multiple tasks per day.
* Individual task completion.
* Day completion logic.
* New roadmap insertion from first incomplete day.
* Future task shifting.
* Fixed total duration.
* Basic rescheduling/rebalancing.
* Progress tracking.
* Clean game-like roadmap UI.

---

## 24. Post-MVP Scope
* Push/email reminders.
* Calendar integration.
* Multiple simultaneous roadmaps.
* Advanced streak and achievement system.
* Detailed productivity analytics.
* Voice input.
* Mobile app.
* Advanced AI progress analysis.
* Automatic adaptive scheduling based on historical completion behavior.
* Cloud sync across devices and broader multi-user support.

---

## 25. Edge Cases
* User has completed the entire roadmap and then adds new content.
* User adds new content with duration longer than remaining days.
* A day has unfinished tasks when a new roadmap is inserted.
* User changes daily available time.
* User misses several days.
* AI returns malformed or incomplete structured data.
* New content has dependencies that conflict with the current insertion point.
* Future workload becomes unrealistic after insertion.
* User requests an insertion that would require extending the fixed deadline.
* User tries to modify a completed day.

---

## 26. Acceptance Criteria
1. A user can create an active roadmap from supplied roadmap content and a target duration.
2. The system can create multiple tasks within a single day.
3. A task can be marked complete independently.
4. A day becomes complete only when all required tasks are complete.
5. The system correctly identifies the first incomplete day.
6. A new roadmap begins from the first incomplete day.
7. A new roadmap with duration N occupies N day slots starting at the first incomplete day.
8. Completed days remain unchanged.
9. Original future tasks are shifted/rebalanced instead of being silently discarded.
10. The active roadmap's target duration remains unchanged after a normal insertion.
11. The user can preview a major roadmap change before committing it.
12. AI output is validated before it changes the database.
13. The Roadmap Page clearly communicates completed, current, in-progress, and locked days.
14. The application remains usable even if AI is temporarily unavailable for normal task completion and progress tracking.

---

## 27. Development Order
* Phase 1 — Product specification + UI wireframes
* Phase 2 — Frontend shell and roadmap UI with mock data
* Phase 3 — Database and core CRUD
* Phase 4 — Task/day completion logic
* Phase 5 — Initial AI roadmap generation
* Phase 6 — Roadmap insertion + shifting engine
* Phase 7 — Rescheduling and fixed-duration validation
* Phase 8 — UI polish, animations and gamification
* Phase 9 — Testing and deployment

---

## 28. Product Principle to Preserve During Development
> **“The AI does not decide what I should learn. It helps me actually finish what I have already decided to learn.”**

---

## 29. Implementation Instruction for Coding Agent
When this PRD is provided to a coding agent, it should treat the product rules in Sections 11–15 as core business logic. The coding agent must not change those rules, add major product features, or reinterpret roadmap insertion behavior without explicit approval from the product owner.
