
from .schemas import (
    Exam,
    Student,
    TimeSlot,
    Room,
    ScheduleAssignment,
)
from .constraints import (
    find_conflicting_exams,
    validate_time_slots,
    validate_exam_data,
)


def validate_schedule(
    exams: list[Exam],
    students: list[Student],
    time_slots: list[TimeSlot],
    rooms: list[Room],
    assignments: list[ScheduleAssignment],
) -> list[str]:
    """
    Independently validate a generated timetable.

    Returns an empty list if all implemented checks pass.
    """

    errors = []

    errors.extend(validate_time_slots(time_slots))
    errors.extend(validate_exam_data(exams, students, rooms))

    exam_ids = [exam.exam_id for exam in exams]
    slot_ids = [slot.slot_id for slot in time_slots]
    room_ids = [room.room_id for room in rooms]

    if len({item.exam_id for item in assignments}) != len(assignments):
        errors.append("An exam has multiple schedule assignments.")

    assignment_by_exam = {}

    for assignment in assignments:
        assignment_by_exam.setdefault(
            assignment.exam_id, []
        ).append(assignment)

        if assignment.exam_id not in exam_ids:
            errors.append(
                f"Unknown exam assigned: {assignment.exam_id}"
            )

        if assignment.slot_id not in slot_ids:
            errors.append(
                f"Unknown time slot: {assignment.slot_id}"
            )

        if not assignment.room_ids:
            errors.append(
                f"Exam {assignment.exam_id} has no assigned rooms."
            )

        if len(assignment.room_ids) != len(set(assignment.room_ids)):
            errors.append(
                f"Exam {assignment.exam_id} has duplicate room assignments."
            )

        for room_id in assignment.room_ids:
            if room_id not in room_ids:
                errors.append(
                    f"Unknown room assigned: {room_id}"
                )

    for exam_id in exam_ids:
        count = len(assignment_by_exam.get(exam_id, []))
        if count != 1:
            errors.append(
                f"Exam {exam_id} must have exactly one assignment; "
                f"found {count}."
            )

    exam_by_id = {exam.exam_id: exam for exam in exams}
    slot_by_id = {slot.slot_id: slot for slot in time_slots}
    room_by_id = {room.room_id: room for room in rooms}

    # Validate duration, capacity, and room availability.
    for exam_id, exam_assignments in assignment_by_exam.items():
        exam = exam_by_id.get(exam_id)
        if exam is None:
            continue

        for assignment in exam_assignments:
            slot = slot_by_id.get(assignment.slot_id)
            if slot is None:
                continue

            start = _minutes(slot.start_time)
            end = _minutes(slot.end_time)

            if start is None or end is None:
                continue

            if end - start < exam.duration_minutes:
                errors.append(
                    f"Exam {exam_id} exceeds the duration of "
                    f"slot {slot.slot_id}."
                )

            assigned_rooms = [
                room_by_id[room_id]
                for room_id in assignment.room_ids
                if room_id in room_by_id
            ]

            capacity = sum(room.capacity for room in assigned_rooms)

            if capacity < len(exam.enrolled_student_ids):
                errors.append(
                    f"Insufficient room capacity for exam {exam_id}: "
                    f"{capacity} seats for "
                    f"{len(exam.enrolled_student_ids)} students."
                )

            for room in assigned_rooms:
                if assignment.slot_id in room.unavailable_slot_ids:
                    errors.append(
                        f"Room {room.room_id} is unavailable for "
                        f"slot {assignment.slot_id}."
                    )

    # Student conflicts: exams sharing students cannot use the same slot.
    for exam_a_id, exam_b_id in find_conflicting_exams(exams):
        assignments_a = assignment_by_exam.get(exam_a_id, [])
        assignments_b = assignment_by_exam.get(exam_b_id, [])

        for a in assignments_a:
            for b in assignments_b:
                if a.slot_id == b.slot_id:
                    errors.append(
                        f"Student conflict: exams {exam_a_id} and "
                        f"{exam_b_id} use the same slot."
                    )

    # A room cannot be used by two exams in overlapping periods.
    for i in range(len(assignments)):
        a = assignments[i]
        slot_a = slot_by_id.get(a.slot_id)

        if slot_a is None:
            continue

        for j in range(i + 1, len(assignments)):
            b = assignments[j]
            slot_b = slot_by_id.get(b.slot_id)

            if slot_b is None or slot_a.date != slot_b.date:
                continue

            if not set(a.room_ids).intersection(b.room_ids):
                continue

            start_a = _minutes(slot_a.start_time)
            end_a = _minutes(slot_a.end_time)
            start_b = _minutes(slot_b.start_time)
            end_b = _minutes(slot_b.end_time)

            if None in (start_a, end_a, start_b, end_b):
                continue

            if start_a < end_b and start_b < end_a:
                errors.append(
                    f"Room conflict: exams {a.exam_id} and {b.exam_id} "
                    f"book the same room during overlapping slots."
                )

    return errors


def _minutes(time_value: str) -> int | None:
    """Convert HH:MM to minutes after midnight."""

    try:
        hour, minute = map(int, time_value.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        return hour * 60 + minute
    except (ValueError, AttributeError):
        return None

