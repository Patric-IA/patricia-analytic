from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from app.services import evaluate_compatibility
from app.models import PersonModel
from openai import OpenAI
import os
import re
from datetime import datetime
from typing import Dict

router = APIRouter()

@router.post("/matchmaking") 
async def matchmaking(person1: PersonModel, person2: PersonModel):
    # Llama a la función de evaluación de compatibilidad con los modelos de Pydantic
    compatibility_result = evaluate_compatibility(person1, person2)
    return {"compatibility_score": compatibility_result}
