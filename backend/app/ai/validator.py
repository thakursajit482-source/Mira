from typing import List
from backend.app.ai.schemas import GeneratedRoadmap, RoadmapGenerationRequest


class AIValidationError(Exception):
    """Exception raised when untrusted AI output violates structural or workload invariants."""

    def __init__(self, message: str, details: List[str] = None):
        self.message = message
        self.details = details or [message]
        full_msg = f"{message} {'; '.join(self.details)}" if details else message
        super().__init__(full_msg)


class AIValidator:
    """
    Dedicated validation layer for untrusted AI output.
    Enforces strict structural, sequential, and workload constraints before database persistence.
    """

    @classmethod
    def validate(
        cls,
        generated: GeneratedRoadmap,
        request: RoadmapGenerationRequest,
        daily_capacity: int,
    ) -> None:
        """
        Validate generated roadmap output against request constraints and Mira business rules.
        Raises AIValidationError if any validation check fails.
        """
        errors: List[str] = []

        # 1. Title validation
        if not generated.title or not generated.title.strip():
            errors.append("Roadmap title is missing or empty.")

        # 2. Target duration validation
        if generated.target_duration_days != request.target_duration_days:
            errors.append(
                f"Generated target duration ({generated.target_duration_days}) does not match "
                f"requested duration ({request.target_duration_days})."
            )

        # 3. Days list existence & exact count
        if not generated.days:
            errors.append("Generated roadmap contains no days.")
        elif len(generated.days) != request.target_duration_days:
            errors.append(
                f"Generated {len(generated.days)} days, but requested exactly "
                f"{request.target_duration_days} days."
            )

        # 4. Day numbering and uniqueness
        if generated.days:
            day_numbers = [d.day_number for d in generated.days]
            if len(day_numbers) != len(set(day_numbers)):
                errors.append("Generated roadmap contains duplicate day numbers.")

            expected_day_numbers = list(range(1, request.target_duration_days + 1))
            sorted_day_numbers = sorted(day_numbers)
            if sorted_day_numbers != expected_day_numbers:
                errors.append(
                    f"Day numbers must be strictly consecutive from 1 to {request.target_duration_days}. "
                    f"Found: {sorted_day_numbers}."
                )

        # 5. Day tasks & workload validation
        for day in generated.days:
            if not day.tasks:
                errors.append(f"Day {day.day_number} contains no tasks.")
                continue

            order_indices = []
            day_total_minutes = 0

            for task_idx, task in enumerate(day.tasks):
                if not task.title or not task.title.strip():
                    errors.append(f"Day {day.day_number}, task #{task_idx + 1} is missing a title.")

                if task.estimated_minutes is None or task.estimated_minutes <= 0:
                    errors.append(
                        f"Day {day.day_number}, task '{task.title}' has invalid estimated minutes: "
                        f"{task.estimated_minutes}. Must be greater than zero."
                    )
                else:
                    day_total_minutes += task.estimated_minutes

                order_indices.append(task.order_index)

            # Task order uniqueness within day
            if len(order_indices) != len(set(order_indices)):
                errors.append(f"Day {day.day_number} contains duplicate task order_index values.")

            expected_orders = list(range(len(day.tasks)))
            if sorted(order_indices) != expected_orders:
                errors.append(
                    f"Day {day.day_number} task order_index values must be consecutive starting from 0. "
                    f"Found: {sorted(order_indices)}."
                )

            # Workload validation against daily capacity
            if day_total_minutes > daily_capacity:
                errors.append(
                    f"Day {day.day_number} workload ({day_total_minutes} mins) exceeds daily available "
                    f"capacity ({daily_capacity} mins)."
                )

        if errors:
            raise AIValidationError(
                message=f"AI output validation failed with {len(errors)} error(s).",
                details=errors,
            )
