
from .schemas import (
    Exam,
    Student,
    TimeSlot,
    Room,
    ScheduleAssignment,
    SchedulingRules,
)
from .scheduler import generate_schedule
from .validator import validate_schedule
from .constraints import (
    validate_exam_data,
    validate_time_slots,
    diagnose_scheduling_inputs,
)


def run_scheduling_agent(
    exams: list[Exam],
    students: list[Student],
    time_slots: list[TimeSlot],
    rooms: list[Room],
    rules: SchedulingRules | None = None,
) -> dict:
    """
    Coordinate input validation, schedule generation,
    and independent schedule validation.

    Uses the same scheduling rules for generation and validation.
    Provides diagnostic suggestions when scheduling fails.
    """

    print("Agent: Starting exam scheduling...")

    # Use default rules when no custom rules are provided.
    if rules is None:
        rules = SchedulingRules()

    # Step 1: Validate input data.
    input_errors = validate_time_slots(time_slots)
    input_errors.extend(
        validate_exam_data(exams, students, rooms)
    )

    if input_errors:
        return {
            "success": False,
            "message": "Input validation failed.",
            "assignments": [],
            "errors": input_errors,
        }

    # Step 2: Generate a timetable.
    assignments = generate_schedule(
        exams=exams,
        time_slots=time_slots,
        rooms=rooms,
        students=students,
        rules=rules,
    )

    # Step 3: Diagnose scheduling failure if no timetable is found.
    if assignments is None:
        suggestions = diagnose_scheduling_inputs(
            exams=exams,
            students=students,
            time_slots=time_slots,
            rooms=rooms,
        )

        errors = [
            (
                "The scheduling solver could not find a valid "
                "timetable satisfying all constraints."
            )
        ]

        if suggestions:
            errors.extend(suggestions)
        else:
            errors.append(
                "Review the scheduling rules, student conflicts, "
                "room availability, and available time slots."
            )

        return {
            "success": False,
            "message": (
                "No feasible timetable could be generated "
                "with the current inputs and scheduling rules."
            ),
            "assignments": [],
            "errors": errors,
        }

    print("Agent: Timetable generated. Validating...")

    # Step 4: Independently validate the generated timetable.
    errors = validate_schedule(
        exams=exams,
        students=students,
        time_slots=time_slots,
        rooms=rooms,
        assignments=assignments,
        rules=rules,
    )

    if errors:
        return {
            "success": False,
            "message": "Timetable validation failed.",
            "assignments": [],
            "errors": errors,
        }

    print("Agent: Validation successful.")

    return {
        "success": True,
        "message": (
            "Timetable generated and validated successfully."
        ),
        "assignments": assignments,
        "errors": [],
    }
