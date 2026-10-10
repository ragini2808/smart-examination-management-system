
from datetime import datetime

from .schemas import Exam, Student, TimeSlot, Room


def find_conflicting_exams(
    exams: list[Exam],
) -> list[tuple[str, str]]:
    """Find exam pairs that share at least one student."""

    conflicts = []

    for i in range(len(exams)):
        for j in range(i + 1, len(exams)):
            students_a = set(exams[i].enrolled_student_ids)
            students_b = set(exams[j].enrolled_student_ids)

            if students_a.intersection(students_b):
                conflicts.append(
                    (exams[i].exam_id, exams[j].exam_id)
                )

    return conflicts


def validate_time_slots(
    time_slots: list[TimeSlot],
) -> list[str]:
    """Validate slot IDs, time formats, ranges, and overlaps."""

    errors = []
    seen_ids = set()
    parsed_slots = []

    for slot in time_slots:
        if slot.slot_id in seen_ids:
            errors.append(
                f"Duplicate time-slot ID: {slot.slot_id}"
            )
        seen_ids.add(slot.slot_id)

        try:
            start = datetime.strptime(
                slot.start_time, "%H:%M"
            )
            end = datetime.strptime(
                slot.end_time, "%H:%M"
            )
            datetime.strptime(slot.date, "%Y-%m-%d")
        except ValueError:
            errors.append(
                f"Invalid date or time format for slot "
                f"{slot.slot_id}. Use YYYY-MM-DD and HH:MM."
            )
            continue

        if start >= end:
            errors.append(
                f"Invalid time range for slot {slot.slot_id}."
            )
            continue

        parsed_slots.append((slot, start, end))

    for i in range(len(parsed_slots)):
        slot_a, start_a, end_a = parsed_slots[i]

        for j in range(i + 1, len(parsed_slots)):
            slot_b, start_b, end_b = parsed_slots[j]

            if slot_a.date != slot_b.date:
                continue

            if start_a < end_b and start_b < end_a:
                errors.append(
                    f"Slots {slot_a.slot_id} and "
                    f"{slot_b.slot_id} overlap on {slot_a.date}."
                )

    return errors


def validate_exam_data(
    exams: list[Exam],
    students: list[Student],
    rooms: list[Room],
) -> list[str]:
    """Validate exam IDs, durations, eligibility, and rooms."""

    errors = []

    exam_ids = [exam.exam_id for exam in exams]
    student_ids = [student.student_id for student in students]
    room_ids = [room.room_id for room in rooms]

    if len(exam_ids) != len(set(exam_ids)):
        errors.append("Duplicate exam IDs found.")

    if len(student_ids) != len(set(student_ids)):
        errors.append("Duplicate student IDs found.")

    if len(room_ids) != len(set(room_ids)):
        errors.append("Duplicate room IDs found.")

    student_by_id = {
        student.student_id: student for student in students
    }

    for exam in exams:
        if exam.duration_minutes <= 0:
            errors.append(
                f"Exam {exam.exam_id} must have a positive duration."
            )

        for student_id in exam.enrolled_student_ids:
            student = student_by_id.get(student_id)

            if student is None:
                errors.append(
                    f"Exam {exam.exam_id} references unknown "
                    f"student {student_id}."
                )
                continue

            if (
                exam.eligible_department is not None
                and student.department != exam.eligible_department
            ):
                errors.append(
                    f"Student {student_id} is not eligible for "
                    f"exam {exam.exam_id}: department mismatch."
                )

            if (
                exam.eligible_semester is not None
                and student.semester != exam.eligible_semester
            ):
                errors.append(
                    f"Student {student_id} is not eligible for "
                    f"exam {exam.exam_id}: semester mismatch."
                )

    for room in rooms:
        if room.capacity <= 0:
            errors.append(
                f"Room {room.room_id} must have positive capacity."
            )

    # Check whether combined room capacity can accommodate each exam.
    total_room_capacity = sum(
        room.capacity for room in rooms
        if room.capacity > 0
    )

    for exam in exams:
        student_count = len(set(exam.enrolled_student_ids))

        if student_count > total_room_capacity:
            errors.append(
                f"Exam {exam.exam_id} has {student_count} enrolled "
                f"students, but the total capacity of all rooms is "
                f"only {total_room_capacity}."
            )

    return errors


def diagnose_scheduling_inputs(
    exams: list[Exam],
    students: list[Student],
    time_slots: list[TimeSlot],
    rooms: list[Room],
) -> list[str]:
    """Identify common input problems that can prevent scheduling."""

    suggestions = []

    student_by_id = {
        student.student_id: student
        for student in students
    }

    total_room_capacity = sum(
        room.capacity for room in rooms
        if room.capacity > 0
    )

    if exams and not time_slots:
        suggestions.append(
            "No time slots are available. Add valid exam time slots."
        )

    if exams and not rooms:
        suggestions.append(
            "No rooms are available. Add suitable examination rooms."
        )

    # Check each exam for common input problems.
    for exam in exams:
        enrolled_count = len(set(exam.enrolled_student_ids))

        if enrolled_count > total_room_capacity:
            suggestions.append(
                f"Exam {exam.exam_id} needs {enrolled_count} seats, "
                f"but the combined room capacity is "
                f"{total_room_capacity}. Add suitable rooms."
            )

        # Check whether at least one slot is long enough.
        if exam.duration_minutes > 0 and time_slots:
            long_enough_slots = []

            for slot in time_slots:
                try:
                    start = datetime.strptime(
                        slot.start_time, "%H:%M"
                    )
                    end = datetime.strptime(
                        slot.end_time, "%H:%M"
                    )
                except ValueError:
                    continue

                duration_minutes = (
                    end - start
                ).total_seconds() / 60

                if duration_minutes >= exam.duration_minutes:
                    long_enough_slots.append(slot)

            if not long_enough_slots:
                suggestions.append(
                    f"Exam {exam.exam_id} requires "
                    f"{exam.duration_minutes} minutes, but no "
                    f"available slot is long enough."
                )

        # Check for references to unknown students.
        unknown_students = [
            student_id
            for student_id in exam.enrolled_student_ids
            if student_id not in student_by_id
        ]

        if unknown_students:
            suggestions.append(
                f"Exam {exam.exam_id} references unknown students: "
                f"{', '.join(unknown_students)}."
            )

    return suggestions



        


