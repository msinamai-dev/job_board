import re

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

LETTER = r"[^\W\d_]" 

TEXT_RE = re.compile(rf"^{LETTER}+(?:[ '.,\-]+{LETTER}+)*$")
SKILL_RE = re.compile(rf"^{LETTER}(?:{LETTER}|[ .+#/\-])*$")
COMPANY_RE = re.compile(rf"^(?=.*{LETTER})[\w &.,'\-]{{2,100}}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")

import os

ALLOWED_CV_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_CV_SIZE = 5 * 1024 * 1024  # 5 MB

def check_cv(file, required=False):
    """Returns a list of errors."""
    if not file:
        return ["Please upload your CV."] if required else []
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_CV_EXTENSIONS:
        return ["CV must be a PDF, DOCX or TXT file."]
    if file.size > MAX_CV_SIZE:
        return ["CV must be 5 MB or smaller."]
    return []

def check_text(value, label, required=True, max_len=100):
    value = (value or "").strip()
    if not value:
        return [f"{label} is required."] if required else []
    if len(value) > max_len:
        return [f"{label} is too long (maximum {max_len} characters)."]
    if not TEXT_RE.match(value):
        return [f"{label} can only contain letters and spaces (also . , ' -). Numbers are not allowed."]
    return []

from datetime import date, datetime
MIN_SEEKER_AGE = 17
MAX_SEEKER_AGE = 70

def check_dob(value, min_age=MIN_SEEKER_AGE, max_age=MAX_SEEKER_AGE):
    """Returns (date_or_None, [errors])."""
    if not value:
        return None, ["Date of birth is required."]
    try:
        dob = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None, ["Enter a valid date of birth."]
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if dob > today:
        return None, ["Date of birth cannot be in the future."]
    if age < min_age:
        return None, [f"You must be at least {min_age} years old to register."]
    if age > max_age:
        return None, ["Please enter a valid date of birth."]
    return dob, []

def check_company(value):
    value = (value or "").strip()
    if not value:
        return ["Company name is required."]
    if not COMPANY_RE.match(value):
        return ["Company name must contain letters and can only use numbers, spaces and & . , ' -"]
    return []


def check_password(password, username=""):
    errors = []
    if not re.search(r"[a-z]", password):
        errors.append("Password must include a lowercase letter.")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must include an uppercase letter.")
    if not re.search(r"\d", password):
        errors.append("Password must include a number.")
    if not re.search(r"[^\w\s]", password):
        errors.append("Password must include a symbol (e.g. ! @ # $ %).")
    try: 
        validate_password(password, user=User(username=username))
    except ValidationError as e:
        errors.extend(e.messages)
    return errors


def check_skills(skills):
    items = [s.strip() for s in (skills or "").split(",") if s.strip()]
    if not items:
        return ["Please enter at least one skill."]
    bad = [s for s in items if not SKILL_RE.match(s)]
    if bad:
        return [f"Invalid skill(s): {', '.join(bad)}. Skills can only contain letters (and + # . / -)."]
    return []


def check_experience(raw):
    """Returns (value, errors)."""
    raw = (raw or "0").strip() or "0"
    if not raw.isdigit():
        return 0, ["Years of experience must be a whole number."]
    years = int(raw)
    if years > 60:
        return 0, ["Years of experience must be between 0 and 60."]
    return years, []

USERNAME_RE = re.compile(r"^(?=.*[A-Za-z])[A-Za-z0-9_]{3,30}$")


def check_username(username):
    username = (username or "").strip()
    if not re.search(r"[A-Za-z]", username):
        return ["Username must contain at least one letter. Numbers alone are not allowed."]
    if not USERNAME_RE.match(username):
        return ["Username must be 3-30 characters: letters, numbers and underscores only."]
    if User.objects.filter(username__iexact=username).exists():
        return ["That username is already taken."]
    return []