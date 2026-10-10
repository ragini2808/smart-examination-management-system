from dataclasses import dataclass, field


@dataclass
class Student:
    student_id: str
    department: str
    semester: int


@dataclass
class Exam:
    exam_id: str
    subject: str
    enrolled_student_ids: list[str]
    duration_minutes: int
    eligible_department: str | None = None
    eligible_semester: int | None = None
    exam_type: str = "REGULAR"


@dataclass
class TimeSlot:
    slot_id: str
    date: str
    start_time: str
    end_time: str


@dataclass
class Room:
    room_id: str
    room_name: str
    capacity: int
    unavailable_slot_ids: list[str] = field(default_factory=list)


@dataclass
class Invigilator:
    invigilator_id: str
    unavailable_slot_ids: list[str] = field(default_factory=list)


@dataclass
class ScheduleAssignment:
    exam_id: str
    slot_id: str
    room_ids: list[str]


@dataclass
class SchedulingRules:
    max_regular_exams_per_day: int = 2
    max_ese_exams_per_day: int = 1
    ese_gap_days: int = 1
