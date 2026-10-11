
from datetime import date as calendar_date

from .schemas import (
    Exam,
    Student,
    TimeSlot,
    Room,
    ScheduleAssignment,
    SchedulingRules,
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
    rules: SchedulingRules | None = None,
) -> list[str]:
    """
    Independently validate a generated timetable.

    Checks:
    - Input and assignment validity
    - Exam duration and room capacity
    - Room availability and overlapping room bookings
    - Student exam conflicts
    - Daily exam limits per department and semester
    - Required gap between ESE papers

    Returns an empty list if all implemented checks pass.
    """

    errors = []

    if rules is None:
        rules = SchedulingRules()

    # Validate input data.
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

    # Every exam must have exactly one assignment.
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
    student_by_id = {
        student.student_id: student for student in students
    }

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
            student_count = len(exam.enrolled_student_ids)

            if capacity < student_count:
                errors.append(
                    f"Insufficient room capacity for exam {exam_id}: "
                    f"{capacity} seats for {student_count} students."
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

    # A room cannot be used by two exams during overlapping periods.
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
                    "book the same room during overlapping slots."
                )

    # Validate exam type and determine department/semester groups.
    exams_by_group_and_date = {}

    for assignment in assignments:
        exam = exam_by_id.get(assignment.exam_id)
        slot = slot_by_id.get(assignment.slot_id)

        if exam is None or slot is None:
            continue

        exam_type = exam.exam_type.upper()

        if exam_type not in {"REGULAR", "ESE"}:
            errors.append(
                f"Exam {exam.exam_id} has invalid exam type "
                f"{exam.exam_type!r}. Use 'REGULAR' or 'ESE'."
            )
            continue

        groups = set()
        department = exam.eligible_department
        semester = exam.eligible_semester

        # FIX: If either eligibility field is provided, require both.
        if department is not None or semester is not None:
            if department is None or semester is None:
                errors.append(
                    f"Exam {exam.exam_id} must specify both "
                    "eligible_department and eligible_semester."
                )
                continue

            groups.add((department, semester))

        else:
            # Infer groups only when neither explicit field is provided.
            for student_id in exam.enrolled_student_ids:
                student = student_by_id.get(student_id)

                if student is not None:
                    groups.add(
                        (student.department, student.semester)
                    )

        # Group exams by department, semester, and date.
        for department, semester in groups:
            key = (department, semester, slot.date)

            exams_by_group_and_date.setdefault(
                key, []
            ).append(exam)

    # Apply daily limits independently for each department and semester.
    for (department, semester, exam_date), daily_exams in (
        exams_by_group_and_date.items()
    ):
        regular_count = sum(
            exam.exam_type.upper() == "REGULAR"
            for exam in daily_exams
        )

        ese_count = sum(
            exam.exam_type.upper() == "ESE"
            for exam in daily_exams
        )

        if regular_count > rules.max_regular_exams_per_day:
            errors.append(
                f"{department} semester {semester} has "
                f"{regular_count} regular exams on {exam_date}; "
                f"maximum allowed is "
                f"{rules.max_regular_exams_per_day}."
            )

        if ese_count > rules.max_ese_exams_per_day:
            errors.append(
                f"{department} semester {semester} has "
                f"{ese_count} ESE exams on {exam_date}; "
                f"maximum allowed is {rules.max_ese_exams_per_day}."
            )

    # Collect ESE dates for each department/semester.
    ese_dates_by_group = {}

    for (department, semester, exam_date), daily_exams in (
        exams_by_group_and_date.items()
    ):
        if any(
            exam.exam_type.upper() == "ESE"
            for exam in daily_exams
        ):
            ese_dates_by_group.setdefault(
                (department, semester), set()
            ).add(exam_date)

    # Enforce complete calendar days between consecutive ESE dates.
    for (department, semester), date_values in (
        ese_dates_by_group.items()
    ):
        try:
            ordered_dates = sorted(
                calendar_date.fromisoformat(value)
                for value in date_values
            )
        except (ValueError, TypeError):
            # Invalid date formats are reported by input validation.
            continue

        for previous_date, next_date in zip(
            ordered_dates, ordered_dates[1:]
        ):
            complete_gap_days = (
                next_date - previous_date
            ).days - 1

            if complete_gap_days < rules.ese_gap_days:
                errors.append(
                    f"ESE gap violation for {department} semester "
                    f"{semester}: papers on {previous_date} and "
                    f"{next_date} have only {complete_gap_days} "
                    f"complete gap days; {rules.ese_gap_days} required."
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
