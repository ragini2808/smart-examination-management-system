
from datetime import date as calendar_date

from ortools.sat.python import cp_model

from .schemas import (
    Exam,
    Student,
    TimeSlot,
    Room,
    ScheduleAssignment,
    SchedulingRules,
)

from .constraints import find_conflicting_exams, validate_time_slots


def generate_schedule(
    exams: list[Exam],
    time_slots: list[TimeSlot],
    rooms: list[Room],
    students: list[Student] | None = None,
    rules: SchedulingRules | None = None,
) -> list[ScheduleAssignment] | None:
    """
    Generate an exam timetable using OR-Tools CP-SAT.

    Enforces:
    - One time slot per exam.
    - Sufficient combined room capacity.
    - Room availability and no double booking.
    - No same-slot conflicts between exams sharing students.
    - Daily exam limits per department and semester.
    - Configurable calendar-day gaps between ESE papers.

    Returns None if no feasible timetable can be generated.
    """

    if not exams:
        return []

    if not time_slots or not rooms:
        return None

    if validate_time_slots(time_slots):
        return None

    if rules is None:
        rules = SchedulingRules()

    if (
        rules.max_regular_exams_per_day < 0
        or rules.max_ese_exams_per_day < 0
        or rules.ese_gap_days < 0
    ):
        return None

    students = students or []

    # Validate exam types, durations, and available slot lengths.
    for exam in exams:
        if exam.exam_type.upper() not in {"REGULAR", "ESE"}:
            return None

        if exam.duration_minutes <= 0:
            return None

        # FIX: Explicit eligibility must contain both fields.
        department = exam.eligible_department
        semester = exam.eligible_semester

        if (department is None) != (semester is None):
            return None

        if not any(
            _slot_duration(slot) >= exam.duration_minutes
            for slot in time_slots
        ):
            return None

    # Identify each exam's department/semester groups.
    student_by_id = {
        student.student_id: student
        for student in students
    }

    exam_groups: dict[int, set[tuple[str, int]]] = {}

    for index, exam in enumerate(exams):
        groups_for_exam = set()

        department = exam.eligible_department
        semester = exam.eligible_semester

        # FIX: If either field is supplied, both must be supplied.
        if department is not None or semester is not None:
            if department is None or semester is None:
                return None

            groups_for_exam.add((department, semester))

        else:
            # Infer groups only when neither eligibility field is set.
            for student_id in exam.enrolled_student_ids:
                student = student_by_id.get(student_id)

                if student is not None:
                    groups_for_exam.add(
                        (student.department, student.semester)
                    )

        exam_groups[index] = groups_for_exam

    model = cp_model.CpModel()

    # assign_slot[(exam_index, slot_index)] indicates an exam's slot.
    assign_slot = {}

    for e, exam in enumerate(exams):
        valid_slots = []

        for s, slot in enumerate(time_slots):
            if _slot_duration(slot) >= exam.duration_minutes:
                valid_slots.append(s)
                assign_slot[(e, s)] = model.new_bool_var(
                    f"exam_{e}_slot_{s}"
                )

        if not valid_slots:
            return None

        model.add_exactly_one(
            assign_slot[(e, s)] for s in valid_slots
        )

    # assign_room[(exam_index, slot_index, room_index)] indicates
    # whether a room is used by an exam in a particular slot.
    assign_room = {}

    for e, exam in enumerate(exams):
        for s, slot in enumerate(time_slots):
            if (e, s) not in assign_slot:
                continue

            for r, room in enumerate(rooms):
                if slot.slot_id in room.unavailable_slot_ids:
                    continue

                assign_room[(e, s, r)] = model.new_bool_var(
                    f"exam_{e}_slot_{s}_room_{r}"
                )

                model.add(
                    assign_room[(e, s, r)] <= assign_slot[(e, s)]
                )

            room_vars = [
                assign_room[(e, s, r)]
                for r in range(len(rooms))
                if (e, s, r) in assign_room
            ]

            # Combined room capacity must be sufficient.
            model.add(
                sum(
                    rooms[r].capacity * assign_room[(e, s, r)]
                    for r in range(len(rooms))
                    if (e, s, r) in assign_room
                )
                >= len(exam.enrolled_student_ids) * assign_slot[(e, s)]
            )

            # Every scheduled exam must use at least one room.
            model.add(sum(room_vars) >= assign_slot[(e, s)])

    # Exams sharing students cannot use the same time slot.
    exam_index = {
        exam.exam_id: i
        for i, exam in enumerate(exams)
    }

    for exam_a_id, exam_b_id in find_conflicting_exams(exams):
        a = exam_index[exam_a_id]
        b = exam_index[exam_b_id]

        for s in range(len(time_slots)):
            if (a, s) in assign_slot and (b, s) in assign_slot:
                model.add(
                    assign_slot[(a, s)] + assign_slot[(b, s)] <= 1
                )

    # A room cannot be used by multiple exams in the same slot.
    for s in range(len(time_slots)):
        for r in range(len(rooms)):
            room_usage = [
                assign_room[(e, s, r)]
                for e in range(len(exams))
                if (e, s, r) in assign_room
            ]

            if room_usage:
                model.add_at_most_one(room_usage)

    # Group available slots by actual calendar date.
    slots_by_date = {}

    for s, slot in enumerate(time_slots):
        try:
            parsed_date = calendar_date.fromisoformat(slot.date)
        except (ValueError, TypeError):
            return None

        slots_by_date.setdefault(parsed_date, []).append(s)

    ordered_dates = sorted(slots_by_date)

    # Enforce daily limits independently for each department/semester.
    groups = set()

    for exam_group_set in exam_groups.values():
        groups.update(exam_group_set)

    for department, semester in groups:
        group_exams = [
            e
            for e in range(len(exams))
            if (department, semester) in exam_groups[e]
        ]

        for exam_date in ordered_dates:
            slot_indices = slots_by_date[exam_date]

            for exam_type, daily_limit in (
                ("REGULAR", rules.max_regular_exams_per_day),
                ("ESE", rules.max_ese_exams_per_day),
            ):
                daily_exam_vars = [
                    assign_slot[(e, s)]
                    for e in group_exams
                    if exams[e].exam_type.upper() == exam_type
                    for s in slot_indices
                    if (e, s) in assign_slot
                ]

                if daily_exam_vars:
                    model.add(
                        sum(daily_exam_vars) <= daily_limit
                    )

    # ESE gap constraint:
    # Required complete calendar days between ESE papers for the
    # same department/semester must remain free of that group's ESEs.
    # Other department/semester groups can still hold exams.
    if rules.ese_gap_days > 0:
        for department, semester in groups:
            group_ese_exams = [
                e
                for e in range(len(exams))
                if (
                    (department, semester) in exam_groups[e]
                    and exams[e].exam_type.upper() == "ESE"
                )
            ]

            for i, first_date in enumerate(ordered_dates):
                for second_date in ordered_dates[i + 1:]:
                    complete_days_between = (
                        second_date - first_date
                    ).days - 1

                    if complete_days_between >= rules.ese_gap_days:
                        continue

                    first_day_vars = [
                        assign_slot[(e, s)]
                        for e in group_ese_exams
                        for s in slots_by_date[first_date]
                        if (e, s) in assign_slot
                    ]

                    second_day_vars = [
                        assign_slot[(e, s)]
                        for e in group_ese_exams
                        for s in slots_by_date[second_date]
                        if (e, s) in assign_slot
                    ]

                    if first_day_vars and second_day_vars:
                        model.add(
                            sum(first_day_vars)
                            + sum(second_day_vars)
                            <= 1
                        )

    # Solve the timetable model.
    solver = cp_model.CpSolver()
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    assignments = []

    for e, exam in enumerate(exams):
        for s, slot in enumerate(time_slots):
            if (
                (e, s) in assign_slot
                and solver.value(assign_slot[(e, s)])
            ):
                selected_rooms = [
                    rooms[r].room_id
                    for r in range(len(rooms))
                    if (
                        (e, s, r) in assign_room
                        and solver.value(assign_room[(e, s, r)])
                    )
                ]

                assignments.append(
                    ScheduleAssignment(
                        exam_id=exam.exam_id,
                        slot_id=slot.slot_id,
                        room_ids=selected_rooms,
                    )
                )
                break

    return assignments


def _slot_duration(slot: TimeSlot) -> int:
    """Return the duration of a time slot in minutes."""

    start_hour, start_minute = map(int, slot.start_time.split(":"))
    end_hour, end_minute = map(int, slot.end_time.split(":"))

    return (
        end_hour * 60 + end_minute
        - start_hour * 60 - start_minute
    )
