from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from app.services import evaluate_compatibility
from app.models import MatchmakingRequest
from openai import OpenAI
import os
import re
from datetime import datetime
from typing import Dict
from app.models import Person

router = APIRouter()

@router.post("/matchmaking")
async def matchmaking(request: MatchmakingRequest):
    compatibility_score = evaluate_compatibility(request.person1.dict(), request.person2.dict())
    return {"compatibility_score": compatibility_score}
