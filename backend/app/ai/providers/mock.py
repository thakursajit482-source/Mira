from typing import List
from backend.app.ai.base import AIProvider
from backend.app.ai.schemas import (
    RoadmapGenerationRequest,
    GeneratedRoadmap,
    GeneratedDay,
    GeneratedTask,
)


class MockAIProvider(AIProvider):
    """
    Deterministic mock AI provider for development, CI, and offline testing.
    Generates structured, realistic learning roadmaps tailored to the requested goal,
    duration, and daily available capacity without external API calls or keys.
    """

    def generate_roadmap(
        self,
        request: RoadmapGenerationRequest,
        effective_daily_capacity: int,
    ) -> GeneratedRoadmap:
        """
        Generate a deterministic, structured roadmap based on the request parameters.
        Produces exactly request.target_duration_days days with realistic workloads.
        """
        goal = request.goal.strip()
        duration = request.target_duration_days
        capacity = max(30, effective_daily_capacity)

        # Determine phase milestones based on duration
        days: List[GeneratedDay] = []

        # Task duration breakdown fitting within daily capacity
        # For example, if capacity is 120 mins: Task 1 = 60 mins, Task 2 = 60 mins
        # If capacity is 60 mins: Task 1 = 30 mins, Task 2 = 30 mins
        if capacity >= 60:
            task1_mins = capacity // 2
            task2_mins = capacity - task1_mins
            has_two_tasks = True
        else:
            task1_mins = capacity
            task2_mins = 0
            has_two_tasks = False

        for day_num in range(1, duration + 1):
            phase_name, phase_cat = self._get_phase_info(day_num, duration, goal)
            day_title = f"{phase_name} - Part {day_num}"

            tasks: List[GeneratedTask] = []
            # Task 1: Theory & Concept Study
            tasks.append(
                GeneratedTask(
                    title=f"Study: {goal} - {phase_name} (Day {day_num})",
                    description=f"Core concepts, syntax, and principles for {phase_name.lower()}.",
                    estimated_minutes=task1_mins,
                    category=phase_cat,
                    order_index=0,
                )
            )

            # Task 2: Hands-on Practice
            if has_two_tasks:
                tasks.append(
                    GeneratedTask(
                        title=f"Practice: {phase_name} Exercises (Day {day_num})",
                        description=f"Practical hands-on exercises and coding challenges for {goal}.",
                        estimated_minutes=task2_mins,
                        category=f"{phase_cat} Practice",
                        order_index=1,
                    )
                )

            days.append(
                GeneratedDay(
                    day_number=day_num,
                    title=day_title,
                    tasks=tasks,
                )
            )

        context_suffix = f" ({request.context})" if request.context else ""
        return GeneratedRoadmap(
            title=f"Roadmap: {goal}{context_suffix}",
            description=(
                f"A structured {duration}-day roadmap for '{goal}' "
                f"designed for {capacity} minutes of daily study."
            ),
            target_duration_days=duration,
            days=days,
        )

    @staticmethod
    def _get_phase_info(day_num: int, total_days: int, goal: str) -> tuple[str, str]:
        """Determine logical phase name and category based on progress through the total duration."""
        if total_days <= 2:
            return ("Foundations & Essentials", "Basics")

        progress = day_num / total_days
        if progress <= 0.25:
            return ("Foundations & Setup", "Fundamentals")
        elif progress <= 0.60:
            return ("Core Concepts & Implementation", "Core")
        elif progress <= 0.85:
            return ("Advanced Topics & Architecture", "Advanced")
        else:
            return ("Capstone Project & Review", "Project")
