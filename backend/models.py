from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    Time,
    ForeignKey,
)
from database import Base


# =====================================================
# 1. USER MODEL
# Existing authentication system
# =====================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)


# =====================================================
# 2. STUDENT MODEL
# =====================================================

class Student(Base):
    __tablename__ = "students"

    student_id = Column(String(50), primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        unique=True,
        nullable=True,
    )

    department = Column(String(100), nullable=False)
    semester = Column(Integer, nullable=False)


# =====================================================
# 3. EXAM MODEL
# =====================================================

class Exam(Base):
    __tablename__ = "exams"

    exam_id = Column(String(50), primary_key=True)
    subject = Column(String(150), nullable=False)
    duration_minutes = Column(Integer, nullable=False)

    eligible_department = Column(String(100), nullable=True)
    eligible_semester = Column(Integer, nullable=True)

    exam_type = Column(
        String(20),
        nullable=False,
        default="REGULAR",
    )


# =====================================================
# 4. EXAM ENROLLMENT MODEL
# Connects students to exams
# =====================================================

class ExamEnrollment(Base):
    __tablename__ = "exam_enrollments"

    exam_id = Column(
        String(50),
        ForeignKey("exams.exam_id"),
        primary_key=True,
    )

    student_id = Column(
        String(50),
        ForeignKey("students.student_id"),
        primary_key=True,
    )


# =====================================================
# 5. ROOM MODEL
# =====================================================

class Room(Base):
    __tablename__ = "rooms"

    room_id = Column(String(50), primary_key=True)
    room_name = Column(String(100), nullable=False)
    capacity = Column(Integer, nullable=False)


# =====================================================
# 6. TIME SLOT MODEL
# =====================================================

class TimeSlot(Base):
    __tablename__ = "time_slots"

    slot_id = Column(String(50), primary_key=True)
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)


# =====================================================
# 7. ROOM UNAVAILABILITY MODEL
# Records rooms unavailable for particular time slots
# =====================================================

class RoomUnavailableSlot(Base):
    __tablename__ = "room_unavailable_slots"

    room_id = Column(
        String(50),
        ForeignKey("rooms.room_id"),
        primary_key=True,
    )

    slot_id = Column(
        String(50),
        ForeignKey("time_slots.slot_id"),
        primary_key=True,
    )


# =====================================================
# 8. SCHEDULE ASSIGNMENT MODEL
# Assigns an exam to a time slot
# =====================================================

class ScheduleAssignment(Base):
    __tablename__ = "schedule_assignments"

    exam_id = Column(
        String(50),
        ForeignKey("exams.exam_id"),
        primary_key=True,
    )

    slot_id = Column(
        String(50),
        ForeignKey("time_slots.slot_id"),
        nullable=False,
    )


# =====================================================
# 9. SCHEDULE ASSIGNMENT ROOM MODEL
# Supports multiple rooms for one exam
# =====================================================

class ScheduleAssignmentRoom(Base):
    __tablename__ = "schedule_assignment_rooms"

    exam_id = Column(
        String(50),
        ForeignKey("schedule_assignments.exam_id"),
        primary_key=True,
    )

    room_id = Column(
        String(50),
        ForeignKey("rooms.room_id"),
        primary_key=True,
    )