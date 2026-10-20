from fastapi import APIRouter


router = APIRouter(prefix="/workspace")


SECTIONS = {"today", "food", "workouts", "course", "progress", "ask", "profile", "settings"}


KINDS_SECTION = {"target": "food", "program": "workouts", "workout": "workouts", "activity_log": "workouts",
                 "course": "course", "measurement": "progress", "wellbeing": "today"}
