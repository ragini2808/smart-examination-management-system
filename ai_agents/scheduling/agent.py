
from .schemas import (
    Exam,
    Student,
    TimeSlot,
    Room,
    ScheduleAssignment,
)
from .scheduler import generate_schedule
from .validator import validate_schedule
from .constraints import validate_exam_data, validate_time_slots


def run_scheduling_agent(
    exams: list[Exam],
    students: list[Student],
    time_slots: list[TimeSlot],
    rooms: list[Room],
) -> dict:
    """
    Coordinate input validation, schedule generation,
    and independent schedule validation.
    """

    print("Agent: Starting exam scheduling...")

    # Step 1: Validate the input data before scheduling.
    input_errors = validate_time_slots(time_slots)
    input_errors.extend(validate_exam_data(exams, students, rooms))

    if input_errors:
        return {
            "success": False,
            "message": "Input validation failed.",
            "assignments": [],
            "errors": input_errors,
        }

    # Step 2: Generate a timetable.
    assignments = generate_schedule(exams, time_slots, rooms)

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

    # Step 3: Independently validate the generated timetable.
    errors = validate_schedule(
        exams,
        students,
        time_slots,
        rooms,
        assignments,
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

