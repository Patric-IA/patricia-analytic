from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from app.services import evaluate_compatibility
from pydub import 
from openai import OpenAI
import os
import re
from datetime import datetime
from typing import Dict
from app.models import Person

router = APIRouter()

@router.post("/matchmaking")
async def matchmaking(person1: Person, person2: Person):
    compatibility_result = evaluate_compatibility(person1, person2)
    return compatibility_result
