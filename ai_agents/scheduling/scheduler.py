
from ortools.sat.python import cp_model

from .schemas import Exam, TimeSlot, Room, ScheduleAssignment
from .constraints import find_conflicting_exams, validate_time_slots


def generate_schedule(
    exams: list[Exam],
    time_slots: list[TimeSlot],
    rooms: list[Room],
) -> list[ScheduleAssignment] | None:
    """
    Assign each exam to one time slot and one or more rooms.

    The selected rooms must:
    - Have enough total capacity for enrolled students.
    - Be available during the selected time slot.
    - Not be double-booked for conflicting exams.
    """

    if not exams:
        return []

    if not time_slots or not rooms:
        return None

    if validate_time_slots(time_slots):
        return None

    # Reject exams that cannot fit into any available time slot.
    for exam in exams:
        if exam.duration_minutes <= 0:
            return None

        if not any(
            _slot_duration(slot) >= exam.duration_minutes
            for slot in time_slots
        ):
            return None

    model = cp_model.CpModel()

    # A variable indicates whether an exam uses a particular slot.
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

    # A variable indicates whether an exam uses a room.
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

                # A room can only be assigned when the exam
                # is scheduled in that time slot.
                model.add(
                    assign_room[(e, s, r)] <= assign_slot[(e, s)]
                )

            room_vars = [
                assign_room[(e, s, r)]
                for r in range(len(rooms))
                if (e, s, r) in assign_room
            ]

            # Enough combined room capacity for enrolled students.
            model.add(
                sum(
                    rooms[r].capacity * assign_room[(e, s, r)]
                    for r in range(len(rooms))
                    if (e, s, r) in assign_room
                )
                >= len(exam.enrolled_student_ids) * assign_slot[(e, s)]
            )

            # At least one room when the exam uses this slot.
            model.add(
                sum(room_vars) >= assign_slot[(e, s)]
            )

    # Conflicting exams cannot use the same time slot.
    conflicts = find_conflicting_exams(exams)

    exam_index = {
        exam.exam_id: i for i, exam in enumerate(exams)
    }

    for exam_a_id, exam_b_id in conflicts:
        a = exam_index[exam_a_id]
        b = exam_index[exam_b_id]

        for s in range(len(time_slots)):
            if (a, s) in assign_slot and (b, s) in assign_slot:
                model.add(
                    assign_slot[(a, s)] + assign_slot[(b, s)] <= 1
                )

    # A room cannot be assigned to two exams in the same slot.
    for s in range(len(time_slots)):
        for r in range(len(rooms)):
            room_usage = [
                assign_room[(e, s, r)]
                for e in range(len(exams))
                if (e, s, r) in assign_room
            ]

            if room_usage:
                model.add_at_most_one(room_usage)

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
    """Return the duration of a slot in minutes."""

    start_hour, start_minute = map(int, slot.start_time.split(":"))
    end_hour, end_minute = map(int, slot.end_time.split(":"))

    return (
        end_hour * 60 + end_minute
        - start_hour * 60 - start_minute
    )

