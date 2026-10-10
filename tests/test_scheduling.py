
import unittest
from datetime import date

from ai_agents.scheduling.scheduler import generate_schedule
from ai_agents.scheduling.schemas import (
    Exam,
    Student,
    TimeSlot,
    Room,
    SchedulingRules,
)
from ai_agents.scheduling.agent import run_scheduling_agent


class TestSchedulingAgent(unittest.TestCase):

    def setUp(self):
        self.students = [
            Student("S1", "CSE", 3),
            Student("S2", "CSE", 3),
            Student("S3", "CSE", 3),
        ]

        self.slots = [
            TimeSlot("T1", "2026-11-01", "09:00", "11:00"),
            TimeSlot("T2", "2026-11-01", "12:00", "14:00"),
        ]

        self.rooms = [
            Room("R1", "Room 101", 2),
            Room("R2", "Room 102", 2),
        ]

    # Test 1: A valid timetable is generated.
    def test_valid_schedule(self):
        exams = [
            Exam("E1", "Math", ["S1", "S2"], 60),
            Exam("E2", "DBMS", ["S1", "S3"], 60),
            Exam("E3", "AI", ["S2", "S3"], 60),
        ]

        three_slots = self.slots + [
            TimeSlot("T3", "2026-11-02", "09:00", "11:00")
        ]

        result = run_scheduling_agent(
            exams, self.students, three_slots, self.rooms
        )

        self.assertTrue(result["success"], result["errors"])
        self.assertEqual(len(result["assignments"]), 3)

    # Test 2: Three conflicting exams cannot fit into two slots.
    def test_impossible_schedule(self):
        exams = [
            Exam("E1", "Math", ["S1"], 60),
            Exam("E2", "DBMS", ["S1"], 60),
            Exam("E3", "AI", ["S1"], 60),
        ]

        result = run_scheduling_agent(
            exams, self.students, self.slots, self.rooms
        )

        self.assertFalse(result["success"])

    # Test 3: An empty exam list is handled.
    def test_empty_exam_list(self):
        result = run_scheduling_agent(
            [], self.students, self.slots, self.rooms
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["assignments"], [])

    # Test 4: No time slots means no schedule is possible.
    def test_no_time_slots(self):
        exams = [Exam("E1", "Math", ["S1"], 60)]

        result = run_scheduling_agent(
            exams, self.students, [], self.rooms
        )

        self.assertFalse(result["success"])

    # Test 5: Overlapping time slots must be rejected.
    def test_overlapping_time_slots(self):
        overlapping_slots = [
            TimeSlot("T1", "2026-11-01", "09:00", "11:00"),
            TimeSlot("T2", "2026-11-01", "10:00", "12:00"),
        ]

        exams = [Exam("E1", "Math", ["S1"], 60)]

        result = run_scheduling_agent(
            exams, self.students, overlapping_slots, self.rooms
        )

        self.assertFalse(result["success"])
        self.assertTrue(
            any("overlap" in error.lower() for error in result["errors"])
        )

    # Test 6: Multiple rooms must provide sufficient capacity.
    def test_multiple_room_capacity(self):
        exams = [
            Exam("E1", "Math", ["S1", "S2", "S3"], 60)
        ]

        result = run_scheduling_agent(
            exams, self.students, self.slots, self.rooms
        )

        self.assertTrue(result["success"], result["errors"])

        assignment = result["assignments"][0]
        self.assertGreaterEqual(len(assignment.room_ids), 2)

    # Test 7: An exam cannot fit into a slot that is too short.
    def test_exam_duration_exceeds_available_slots(self):
        short_slots = [
            TimeSlot("T1", "2026-11-01", "09:00", "09:30")
        ]

        exams = [Exam("E1", "Math", ["S1"], 60)]

        result = run_scheduling_agent(
            exams, self.students, short_slots, self.rooms
        )

        self.assertFalse(result["success"])

    # Test 8: An ineligible student must be rejected.
    def test_department_eligibility(self):
        exams = [
            Exam(
                "E1",
                "Advanced Math",
                ["S1"],
                60,
                eligible_department="ECE",
            )
        ]

        result = run_scheduling_agent(
            exams, self.students, self.slots, self.rooms
        )

        self.assertFalse(result["success"])
        self.assertTrue(
            any(
                "department mismatch" in error.lower()
                for error in result["errors"]
            )
        )

    # Test 9: Unavailable rooms cannot be used.
    def test_room_unavailability(self):
        unavailable_rooms = [
            Room("R1", "Room 101", 10, ["T1"]),
        ]

        slots = [
            TimeSlot("T1", "2026-11-01", "09:00", "11:00")
        ]

        exams = [Exam("E1", "Math", ["S1"], 60)]

        result = run_scheduling_agent(
            exams, self.students, slots, unavailable_rooms
        )

        self.assertFalse(result["success"])

    # Test 10: At most two regular exams per department/semester/day.
    def test_regular_daily_limit(self):
        exams = [
            Exam("E1", "Math", ["S1"], 60),
            Exam("E2", "DBMS", ["S2"], 60),
            Exam("E3", "AI", ["S3"], 60),
        ]

        slots = [
            TimeSlot("T1", "2026-11-01", "09:00", "10:00"),
            TimeSlot("T2", "2026-11-01", "11:00", "12:00"),
            TimeSlot("T3", "2026-11-01", "13:00", "14:00"),
        ]

        result = run_scheduling_agent(
            exams, self.students, slots, self.rooms
        )

        self.assertFalse(result["success"])

    # Test 11: At most one ESE exam per department/semester/day.
    def test_ese_daily_limit(self):
        exams = [
            Exam("E1", "Math", ["S1"], 60, exam_type="ESE"),
            Exam("E2", "DBMS", ["S2"], 60, exam_type="ESE"),
        ]

        slots = [
            TimeSlot("T1", "2026-11-01", "09:00", "10:00"),
            TimeSlot("T2", "2026-11-01", "11:00", "12:00"),
        ]

        result = run_scheduling_agent(
            exams, self.students, slots, self.rooms
        )

        self.assertFalse(result["success"])

    # Test 12: ESE exams must have at least one complete day between them.
    def test_ese_gap_between_consecutive_exams(self):
        students = [
            Student("S1", "CSE", 3),
            Student("S2", "CSE", 3),
        ]

        exams = [
            Exam(
                "E1", "Math", ["S1"], 60,
                eligible_department="CSE",
                eligible_semester=3,
                exam_type="ESE",
            ),
            Exam(
                "E2", "DBMS", ["S2"], 60,
                eligible_department="CSE",
                eligible_semester=3,
                exam_type="ESE",
            ),
        ]

        slots = [
            TimeSlot("T1", "2026-11-01", "09:00", "10:00"),
            TimeSlot("T2", "2026-11-02", "09:00", "10:00"),
            TimeSlot("T3", "2026-11-03", "09:00", "10:00"),
        ]

        rooms = [Room("R1", "Room 101", 10)]
        rules = SchedulingRules(ese_gap_days=1)

        result = run_scheduling_agent(
            exams, students, slots, rooms, rules
        )

        self.assertTrue(result["success"], result["errors"])

        assigned_dates = {
            assignment.exam_id: next(
                slot.date
                for slot in slots
                if slot.slot_id == assignment.slot_id
            )
            for assignment in result["assignments"]
        }

        date1 = date.fromisoformat(assigned_dates["E1"])
        date2 = date.fromisoformat(assigned_dates["E2"])
        gap = abs((date2 - date1).days) - 1

        self.assertGreaterEqual(gap, 1)

    # Test 13: ESE exams must have two complete days between them.
    def test_ese_two_day_gap(self):
        students = [
            Student("S1", "CSE", 3),
            Student("S2", "CSE", 3),
        ]

        exams = [
            Exam(
                "E1", "Math", ["S1"], 60,
                eligible_department="CSE",
                eligible_semester=3,
                exam_type="ESE",
            ),
            Exam(
                "E2", "DBMS", ["S2"], 60,
                eligible_department="CSE",
                eligible_semester=3,
                exam_type="ESE",
            ),
        ]

        slots = [
            TimeSlot("T1", "2026-11-01", "09:00", "10:00"),
            TimeSlot("T2", "2026-11-02", "09:00", "10:00"),
            TimeSlot("T3", "2026-11-03", "09:00", "10:00"),
            TimeSlot("T4", "2026-11-04", "09:00", "10:00"),
        ]

        rooms = [Room("R1", "Room 101", 10)]
        rules = SchedulingRules(ese_gap_days=2)

        result = run_scheduling_agent(
            exams, students, slots, rooms, rules
        )

        self.assertTrue(result["success"], result["errors"])

        assigned_dates = {
            assignment.exam_id: next(
                slot.date
                for slot in slots
                if slot.slot_id == assignment.slot_id
            )
            for assignment in result["assignments"]
        }

        date1 = date.fromisoformat(assigned_dates["E1"])
        date2 = date.fromisoformat(assigned_dates["E2"])
        gap = abs((date2 - date1).days) - 1

        self.assertGreaterEqual(
            gap,
            2,
            f"ESE exams have only {gap} complete days between them",
        )

    # Test 14: Another department can schedule an ESE during the gap.
    def test_other_department_can_use_ese_gap_day(self):
        students = [
            Student("S1", "CSE", 3),
            Student("S2", "CSE", 3),
            Student("S3", "ECE", 3),
        ]

        exams = [
            Exam(
                "E1", "Math", ["S1"], 60,
                eligible_department="CSE",
                eligible_semester=3,
                exam_type="ESE",
            ),
            Exam(
                "E2", "DBMS", ["S2"], 60,
                eligible_department="CSE",
                eligible_semester=3,
                exam_type="ESE",
            ),
            Exam(
                "E3", "Electronics", ["S3"], 60,
                eligible_department="ECE",
                eligible_semester=3,
                exam_type="ESE",
            ),
        ]

        slots = [
            TimeSlot("T1", "2026-11-01", "09:00", "10:00"),
            TimeSlot("T2", "2026-11-02", "09:00", "10:00"),
            TimeSlot("T3", "2026-11-04", "09:00", "10:00"),
        ]

        rooms = [Room("R1", "Room 101", 10)]
        rules = SchedulingRules(ese_gap_days=2)

        result = run_scheduling_agent(
            exams, students, slots, rooms, rules
        )

        self.assertTrue(result["success"], result["errors"])

        assigned_dates = {
            assignment.exam_id: next(
                slot.date
                for slot in slots
                if slot.slot_id == assignment.slot_id
            )
            for assignment in result["assignments"]
        }

        self.assertEqual(assigned_dates["E3"], "2026-11-02")

    # Test 15: An infeasible schedule returns a helpful error.
    def test_infeasible_schedule_has_helpful_error(self):
        exams = [
            Exam("E1", "Math", ["S1"], 60),
            Exam("E2", "DBMS", ["S1"], 60),
            Exam("E3", "AI", ["S1"], 60),
        ]

        result = run_scheduling_agent(
            exams, self.students, self.slots, self.rooms
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["assignments"], [])
        self.assertTrue(result["errors"])

        self.assertIn(
            "could not find a valid timetable",
            " ".join(result["errors"]).lower(),
        )

    # Test 16: Insufficient combined room capacity is rejected.
    def test_insufficient_total_room_capacity(self):
        students = [
            Student("S1", "CSE", 3),
            Student("S2", "CSE", 3),
            Student("S3", "CSE", 3),
        ]

        exams = [
            Exam("E1", "Math", ["S1", "S2", "S3"], 60),
        ]

        slots = [
            TimeSlot("T1", "2026-11-01", "09:00", "11:00"),
        ]

        rooms = [
            Room("R1", "Room 101", 1),
            Room("R2", "Room 102", 1),
        ]

        result = run_scheduling_agent(
            exams, students, slots, rooms
        )

        self.assertFalse(result["success"])
        self.assertTrue(
            any(
                "total capacity" in error.lower()
                for error in result["errors"]
            ),
            result["errors"],
        )

    # Test 17: The scheduler uses an alternative available room.
    def test_scheduler_uses_alternative_available_room(self):
        exams = [
            Exam("E1", "Math", ["S1"], 60),
        ]

        slots = [
            TimeSlot("T1", "2026-11-01", "09:00", "10:00"),
        ]

        rooms = [
            Room("R1", "Room 101", 10, ["T1"]),
            Room("R2", "Room 102", 10),
        ]

        result = run_scheduling_agent(
            exams, self.students, slots, rooms
        )

        self.assertTrue(result["success"], result["errors"])
        self.assertEqual(len(result["assignments"]), 1)
        self.assertNotIn("R1", result["assignments"][0].room_ids)
        self.assertIn("R2", result["assignments"][0].room_ids)

    # Test 18: A room cannot be double-booked in the same time slot.
    def test_same_room_not_double_booked(self):
        exams = [
            Exam("E1", "Math", ["S1"], 60),
            Exam("E2", "DBMS", ["S2"], 60),
        ]

        slots = [
            TimeSlot("T1", "2026-11-01", "09:00", "10:00"),
            TimeSlot("T2", "2026-11-01", "11:00", "12:00"),
        ]

        rooms = [
            Room("R1", "Room 101", 10),
        ]

        result = run_scheduling_agent(
            exams, self.students, slots, rooms
        )

        self.assertTrue(result["success"], result["errors"])

        room_slot_pairs = [
            (room_id, assignment.slot_id)
            for assignment in result["assignments"]
            for room_id in assignment.room_ids
        ]

        self.assertEqual(
            len(room_slot_pairs),
            len(set(room_slot_pairs)),
            "A room was assigned to multiple exams in the same slot.",
        )

    # Test 19: The agent explains when no slot is long enough.
    def test_agent_returns_diagnostic_for_slot_too_short(self):
        exam = Exam(
            "E1",
            "Mathematics",
            ["S1"],
            180,
        )

        slot = TimeSlot(
            "T1",
            "2026-11-01",
            "09:00",
            "10:00",
        )

        room = Room("R1", "Room 101", 10)

        result = run_scheduling_agent(
            exams=[exam],
            students=self.students,
            time_slots=[slot],
            rooms=[room],
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["assignments"], [])

        self.assertTrue(
            any(
                "no available slot is long enough" in error.lower()
                for error in result["errors"]
            ),
            msg=f"Expected a slot-duration diagnostic. Got: {result['errors']}",
        )

    
    def test_scheduler_rejects_incomplete_exam_eligibility(self):
        exam = Exam(
            exam_id="E_INCOMPLETE",
            enrolled_student_ids=["S1"],
            duration_minutes=60,
            eligible_department="CSE",
            eligible_semester=None,
            )

        result = generate_schedule(
            exams=[exam],
            time_slots=self.time_slots,
            rooms=self.rooms,
            students=self.students,
            )

        self.assertIsNone(result)



if __name__ == "__main__":
    unittest.main()
