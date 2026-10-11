import os
from pathlib import Path
from datetime import datetime, timedelta, timezone, date, time
from typing import Literal

import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from pwdlib import PasswordHash

from database import get_db

from models import (
    User,
    Student as DBStudent,
    Exam as DBExam,
    ExamEnrollment,
    Room as DBRoom,
    TimeSlot as DBTimeSlot,
    RoomUnavailableSlot,
    ScheduleAssignment as DBScheduleAssignment,
    ScheduleAssignmentRoom,
)

from ai_agents.scheduling.agent import run_scheduling_agent

from ai_agents.scheduling.schemas import (
    Student,
    Exam,
    Room,
    TimeSlot,
    SchedulingRules,
)


# =====================================================
# 1. ENVIRONMENT CONFIGURATION
# =====================================================

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE, override=True)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is missing. Check backend/.env."
    )

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# =====================================================
# 2. FASTAPI APPLICATION
# =====================================================

app = FastAPI(
    title="Smart Examination Management System",
    description="An Agentic AI-based examination management platform",
    version="1.0.0",
)

password_hash = PasswordHash.recommended()
bearer_scheme = HTTPBearer()


# =====================================================
# 3. REQUEST MODELS
# =====================================================

class UserRegistration(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Literal["student", "faculty", "invigilator"]


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class StudentCreate(BaseModel):
    student_id: str = Field(min_length=1, max_length=50)
    user_id: int | None = None
    department: str = Field(min_length=1, max_length=100)
    semester: int = Field(gt=0)


class ExamCreate(BaseModel):
    exam_id: str = Field(min_length=1, max_length=50)
    subject: str = Field(min_length=1, max_length=150)
    enrolled_student_ids: list[str]
    duration_minutes: int = Field(gt=0)
    eligible_department: str | None = None
    eligible_semester: int | None = Field(default=None, gt=0)
    exam_type: Literal["REGULAR", "ESE"] = "REGULAR"


class RoomCreate(BaseModel):
    room_id: str = Field(min_length=1, max_length=50)
    room_name: str = Field(min_length=1, max_length=100)
    capacity: int = Field(gt=0)


class TimeSlotCreate(BaseModel):
    slot_id: str = Field(min_length=1, max_length=50)
    date: date
    start_time: time
    end_time: time


class SchedulingRulesRequest(BaseModel):
    max_regular_exams_per_day: int = Field(default=2, gt=0)
    max_ese_exams_per_day: int = Field(default=1, gt=0)
    ese_gap_days: int = Field(default=1, ge=0)


# =====================================================
# 4. JWT AUTHENTICATION
# =====================================================

def create_access_token(user_email: str) -> str:
    expiration = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": user_email,
        "exp": expiration,
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )

        user_email = payload.get("sub")

        if not user_email:
            raise credentials_exception

    except jwt.InvalidTokenError:
        raise credentials_exception

    user = (
        db.query(User)
        .filter(User.email == user_email)
        .first()
    )

    if user is None:
        raise credentials_exception

    return user


def get_current_admin(
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )

    return current_user


# =====================================================
# 5. BASIC ENDPOINTS
# =====================================================

@app.get("/")
def home():
    return {
        "message": "Smart Examination Management System API is running!",
        "status": "success",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


# =====================================================
# 6. USER REGISTRATION
# =====================================================

@app.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(
    user: UserRegistration,
    db: Session = Depends(get_db),
):
    existing_user = (
        db.query(User)
        .filter(User.email == str(user.email))
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    new_user = User(
        name=user.name,
        email=str(user.email),
        password_hash=password_hash.hash(user.password),
        role=user.role,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to register user.",
        )

    return {
        "message": "User registered successfully",
        "id": new_user.id,
        "name": new_user.name,
        "email": new_user.email,
        "role": new_user.role,
    }


# =====================================================
# 7. USER LOGIN
# =====================================================

@app.post("/login")
def login_user(
    credentials: UserLogin,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.email == str(credentials.email))
        .first()
    )

    if user is None or not password_hash.verify(
        credentials.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(str(user.email))

    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
        },
    }


# =====================================================
# 8. CURRENT USER PROFILE
# =====================================================

@app.get("/me")
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
    }


# =====================================================
# 9. ADMIN: CREATE STUDENT
# =====================================================

@app.post(
    "/admin/students",
    status_code=status.HTTP_201_CREATED,
)
def create_student(
    data: StudentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    existing = (
        db.query(DBStudent)
        .filter(DBStudent.student_id == data.student_id)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Student ID already exists.",
        )

    if data.user_id is not None:
        linked_user = (
            db.query(User)
            .filter(User.id == data.user_id)
            .first()
        )

        if linked_user is None:
            raise HTTPException(
                status_code=404,
                detail="Linked user was not found.",
            )

        if linked_user.role != "student":
            raise HTTPException(
                status_code=400,
                detail="The linked user must have the student role.",
            )

    student = DBStudent(
        student_id=data.student_id,
        user_id=data.user_id,
        department=data.department,
        semester=data.semester,
    )

    try:
        db.add(student)
        db.commit()
        db.refresh(student)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to create student.",
        )

    return {
        "message": "Student created successfully.",
        "student_id": student.student_id,
        "department": student.department,
        "semester": student.semester,
    }


# =====================================================
# 10. ADMIN: LIST STUDENTS
# =====================================================

@app.get("/admin/students")
def list_students(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    students = db.query(DBStudent).all()

    return [
        {
            "student_id": student.student_id,
            "user_id": student.user_id,
            "department": student.department,
            "semester": student.semester,
        }
        for student in students
    ]


# =====================================================
# 11. ADMIN: CREATE EXAM
# =====================================================

@app.post(
    "/admin/exams",
    status_code=status.HTTP_201_CREATED,
)
def create_exam(
    data: ExamCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if db.query(DBExam).filter(
        DBExam.exam_id == data.exam_id
    ).first():
        raise HTTPException(
            status_code=409,
            detail="Exam ID already exists.",
        )

    if len(data.enrolled_student_ids) != len(
        set(data.enrolled_student_ids)
    ):
        raise HTTPException(
            status_code=400,
            detail="Duplicate student IDs are not allowed.",
        )

    students = (
        db.query(DBStudent)
        .filter(
            DBStudent.student_id.in_(
                data.enrolled_student_ids
            )
        )
        .all()
        if data.enrolled_student_ids
        else []
    )

    found_ids = {student.student_id for student in students}

    missing_ids = (
        set(data.enrolled_student_ids) - found_ids
    )

    if missing_ids:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Some student IDs do not exist.",
                "student_ids": sorted(missing_ids),
            },
        )

    new_exam = DBExam(
        exam_id=data.exam_id,
        subject=data.subject,
        duration_minutes=data.duration_minutes,
        eligible_department=data.eligible_department,
        eligible_semester=data.eligible_semester,
        exam_type=data.exam_type,
    )

    try:
        db.add(new_exam)
        db.flush()

        for student_id in data.enrolled_student_ids:
            db.add(
                ExamEnrollment(
                    exam_id=data.exam_id,
                    student_id=student_id,
                )
            )

        db.commit()

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to create exam and enroll students.",
        )

    return {
        "message": "Exam created successfully.",
        "exam_id": data.exam_id,
        "subject": data.subject,
        "enrolled_student_count": len(
            data.enrolled_student_ids
        ),
    }


# =====================================================
# 12. ADMIN: LIST EXAMS
# =====================================================

@app.get("/admin/exams")
def list_exams(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    exams = db.query(DBExam).all()
    result = []

    for exam in exams:
        enrollments = (
            db.query(ExamEnrollment)
            .filter(
                ExamEnrollment.exam_id == exam.exam_id
            )
            .all()
        )

        result.append(
            {
                "exam_id": exam.exam_id,
                "subject": exam.subject,
                "duration_minutes": exam.duration_minutes,
                "eligible_department": exam.eligible_department,
                "eligible_semester": exam.eligible_semester,
                "exam_type": exam.exam_type,
                "enrolled_student_ids": [
                    item.student_id for item in enrollments
                ],
            }
        )

    return result


# =====================================================
# 13. ADMIN: CREATE ROOM
# =====================================================

@app.post(
    "/admin/rooms",
    status_code=status.HTTP_201_CREATED,
)
def create_room(
    data: RoomCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    existing = (
        db.query(DBRoom)
        .filter(DBRoom.room_id == data.room_id)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Room ID already exists.",
        )

    room = DBRoom(
        room_id=data.room_id,
        room_name=data.room_name,
        capacity=data.capacity,
    )

    try:
        db.add(room)
        db.commit()
        db.refresh(room)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to create room.",
        )

    return {
        "message": "Room created successfully.",
        "room_id": room.room_id,
        "room_name": room.room_name,
        "capacity": room.capacity,
    }


# =====================================================
# 14. ADMIN: LIST ROOMS
# =====================================================

@app.get("/admin/rooms")
def list_rooms(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    rooms = db.query(DBRoom).all()

    return [
        {
            "room_id": room.room_id,
            "room_name": room.room_name,
            "capacity": room.capacity,
        }
        for room in rooms
    ]


# =====================================================
# 15. ADMIN: CREATE TIME SLOT
# =====================================================

@app.post(
    "/admin/time-slots",
    status_code=status.HTTP_201_CREATED,
)
def create_time_slot(
    data: TimeSlotCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if data.start_time >= data.end_time:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time.",
        )

    existing = (
        db.query(DBTimeSlot)
        .filter(DBTimeSlot.slot_id == data.slot_id)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Time slot ID already exists.",
        )

    slot = DBTimeSlot(
        slot_id=data.slot_id,
        date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
    )

    try:
        db.add(slot)
        db.commit()
        db.refresh(slot)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to create time slot.",
        )

    return {
        "message": "Time slot created successfully.",
        "slot_id": slot.slot_id,
        "date": slot.date.isoformat(),
        "start_time": slot.start_time.strftime("%H:%M"),
        "end_time": slot.end_time.strftime("%H:%M"),
    }


# =====================================================
# 16. ADMIN: LIST TIME SLOTS
# =====================================================

@app.get("/admin/time-slots")
def list_time_slots(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    slots = db.query(DBTimeSlot).all()

    return [
        {
            "slot_id": slot.slot_id,
            "date": slot.date.isoformat(),
            "start_time": slot.start_time.strftime("%H:%M"),
            "end_time": slot.end_time.strftime("%H:%M"),
        }
        for slot in slots
    ]


# =====================================================
# 17. ADMIN: MARK ROOM UNAVAILABLE
# =====================================================

@app.post(
    "/admin/rooms/{room_id}/unavailable-slots/{slot_id}"
)
def mark_room_unavailable(
    room_id: str,
    slot_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    room = (
        db.query(DBRoom)
        .filter(DBRoom.room_id == room_id)
        .first()
    )

    if room is None:
        raise HTTPException(
            status_code=404,
            detail="Room not found.",
        )

    slot = (
        db.query(DBTimeSlot)
        .filter(DBTimeSlot.slot_id == slot_id)
        .first()
    )

    if slot is None:
        raise HTTPException(
            status_code=404,
            detail="Time slot not found.",
        )

    existing = (
        db.query(RoomUnavailableSlot)
        .filter(
            RoomUnavailableSlot.room_id == room_id,
            RoomUnavailableSlot.slot_id == slot_id,
        )
        .first()
    )

    if existing:
        return {
            "message": "Room is already unavailable for this slot."
        }

    try:
        db.add(
            RoomUnavailableSlot(
                room_id=room_id,
                slot_id=slot_id,
            )
        )
        db.commit()

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to update room availability.",
        )

    return {
        "message": "Room marked unavailable.",
        "room_id": room_id,
        "slot_id": slot_id,
    }


# =====================================================
# 18. ADMIN: GENERATE AND SAVE TIMETABLE
# =====================================================

@app.post("/admin/schedule/generate")
def generate_exam_schedule(
    rules_data: SchedulingRulesRequest | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    db_students = db.query(DBStudent).all()
    db_exams = db.query(DBExam).all()
    db_rooms = db.query(DBRoom).all()
    db_slots = db.query(DBTimeSlot).all()
    db_unavailable = db.query(RoomUnavailableSlot).all()

    unavailable_by_room = {}

    for item in db_unavailable:
        unavailable_by_room.setdefault(
            item.room_id, []
        ).append(item.slot_id)

    students = [
        Student(
            student_id=item.student_id,
            department=item.department,
            semester=item.semester,
        )
        for item in db_students
    ]

    exams = []

    for item in db_exams:
        enrollments = (
            db.query(ExamEnrollment)
            .filter(
                ExamEnrollment.exam_id == item.exam_id
            )
            .all()
        )

        exams.append(
            Exam(
                exam_id=item.exam_id,
                subject=item.subject,
                enrolled_student_ids=[
                    enrollment.student_id
                    for enrollment in enrollments
                ],
                duration_minutes=item.duration_minutes,
                eligible_department=item.eligible_department,
                eligible_semester=item.eligible_semester,
                exam_type=item.exam_type,
            )
        )

    rooms = [
        Room(
            room_id=item.room_id,
            room_name=item.room_name,
            capacity=item.capacity,
            unavailable_slot_ids=unavailable_by_room.get(
                item.room_id, []
            ),
        )
        for item in db_rooms
    ]

    time_slots = [
        TimeSlot(
            slot_id=item.slot_id,
            date=item.date.strftime("%Y-%m-%d"),
            start_time=item.start_time.strftime("%H:%M"),
            end_time=item.end_time.strftime("%H:%M"),
        )
        for item in db_slots
    ]

    rules = SchedulingRules(
        max_regular_exams_per_day=(
            rules_data.max_regular_exams_per_day
            if rules_data else 2
        ),
        max_ese_exams_per_day=(
            rules_data.max_ese_exams_per_day
            if rules_data else 1
        ),
        ese_gap_days=(
            rules_data.ese_gap_days
            if rules_data else 1
        ),
    )

    # Generate and independently validate the timetable.
    result = run_scheduling_agent(
        exams=exams,
        students=students,
        time_slots=time_slots,
        rooms=rooms,
        rules=rules,
    )

    if not result["success"]:
        raise HTTPException(
            status_code=422,
            detail={
                "message": result["message"],
                "errors": result["errors"],
            },
        )

    # Replace the existing timetable only after successful validation.
    try:
        db.query(ScheduleAssignmentRoom).delete(
            synchronize_session=False
        )

        db.query(DBScheduleAssignment).delete(
            synchronize_session=False
        )

        for assignment in result["assignments"]:
            db.add(
                DBScheduleAssignment(
                    exam_id=assignment.exam_id,
                    slot_id=assignment.slot_id,
                )
            )

            for room_id in assignment.room_ids:
                db.add(
                    ScheduleAssignmentRoom(
                        exam_id=assignment.exam_id,
                        room_id=room_id,
                    )
                )

        db.commit()

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to save the generated timetable.",
        )

    return {
        "message": result["message"],
        "assignments": [
            {
                "exam_id": assignment.exam_id,
                "slot_id": assignment.slot_id,
                "room_ids": assignment.room_ids,
            }
            for assignment in result["assignments"]
        ],
        "total_exams_scheduled": len(
            result["assignments"]
        ),
    }


# =====================================================
# 19. ADMIN: VIEW SAVED TIMETABLE
# =====================================================

@app.get("/admin/schedule")
def get_saved_schedule(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    assignments = db.query(DBScheduleAssignment).all()
    result = []

    for assignment in assignments:
        slot = (
            db.query(DBTimeSlot)
            .filter(
                DBTimeSlot.slot_id == assignment.slot_id
            )
            .first()
        )

        exam = (
            db.query(DBExam)
            .filter(
                DBExam.exam_id == assignment.exam_id
            )
            .first()
        )

        room_links = (
            db.query(ScheduleAssignmentRoom)
            .filter(
                ScheduleAssignmentRoom.exam_id
                == assignment.exam_id
            )
            .all()
        )

        result.append(
            {
                "exam_id": assignment.exam_id,
                "subject": exam.subject if exam else None,
                "slot_id": assignment.slot_id,
                "date": slot.date.isoformat() if slot else None,
                "start_time": (
                    slot.start_time.strftime("%H:%M")
                    if slot else None
                ),
                "end_time": (
                    slot.end_time.strftime("%H:%M")
                    if slot else None
                ),
                "room_ids": [
                    item.room_id for item in room_links
                ],
            }
        )

    return {
        "total_assignments": len(result),
        "assignments": result,
    }