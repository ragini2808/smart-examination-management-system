
import unittest

from ai_agents.scheduling.schemas import (
    Exam,
    Student,
    TimeSlot,
    Room,
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
            TimeSlot("T3", "2026-11-01", "15:00", "17:00")
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

        exams = [
            Exam("E1", "Math", ["S1"], 60)
        ]

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
            any("department mismatch" in error.lower()
                for error in result["errors"])
        )

    # Test 9: Unavailable rooms cannot be used.
   
    def test_room_unavailability(self):
        unavailable_rooms = [
        Room("R1", "Room 101", 10, ["T1"]),
        ]

        slots = [
            TimeSlot("T1", "2026-11-01", "09:00", "11:00")
            ]

        exams = [
            Exam("E1", "Math", ["S1"], 60)
            ]

        result = run_scheduling_agent(
            exams, self.students, slots, unavailable_rooms
            )

        self.assertFalse(result["success"])




if __name__ == "__main__":
    unittest.main()

