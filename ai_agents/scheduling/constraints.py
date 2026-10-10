
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

    # Check whether total room capacity can accommodate each exam.
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

        


