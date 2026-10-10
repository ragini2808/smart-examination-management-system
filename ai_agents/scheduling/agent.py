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
from .constraints import validate_exam_data, validate_time_slots


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
    """

    print("Agent: Starting exam scheduling...")

    # Use default rules when the caller does not provide custom rules.
    if rules is None:
        rules = SchedulingRules()

    # Step 1: Validate input data.
    input_errors = validate_time_slots(time_slots)
    input_errors.extend(validate_exam_data(exams, students, rooms))

    if input_errors:
        return {
            "success": False,
            "message": "Input validation failed.",
            "assignments": [],
            "errors": input_errors,
        }

    # Step 2: Generate a timetable using student information and rules.
    assignments = generate_schedule(
        exams=exams,
        time_slots=time_slots,
        rooms=rooms,
        students=students,
        rules=rules,
    )

    if assignments is None:
        return {
            "success": False,
            "message": "No feasible timetable exists.",
            "assignments": [],
            "errors": [
                "Scheduling constraints could not be satisfied."
            ],
        }

    print("Agent: Timetable generated. Validating...")

    # Step 3: Independently validate using the same rules.
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
        "message": "Timetable generated and validated successfully.",
        "assignments": assignments,
        "errors": [],
    }
