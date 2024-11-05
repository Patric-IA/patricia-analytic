import logging
from fastapi import HTTPException, APIRouter
import requests
import os
from app.models import ConversationAnalysisRequest
from app.services import collect_conversation_fragments, analyze_text, analyze_audio, getClassesMongoDB, generate_report
import json

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@router.post("/analyze-conversation")
async def analyze_conversation(request: ConversationAnalysisRequest):
    classes = getClassesMongoDB()
    print(classes)
    logger.info(f"Received request to analyze conversation with ID: {request.conversation_id} for user ID: {request.user_id}")

    # Recuperar los fragmentos de la conversación
    fragments = collect_conversation_fragments(request.conversation_id)
    if not fragments:
        logger.error(f"Conversation with ID: {request.conversation_id} not found.")
        raise HTTPException(
            status_code=404, detail="Conversación no encontrada.")

    # Filtrar fragmentos por el ID del usuario
    user_fragments = [fragment for fragment in fragments if fragment.get(
        "speaker") == request.user_id]
    if not user_fragments:
        logger.error(f"No fragments found for user ID: {request.user_id} in conversation ID: {request.conversation_id}.")
        raise HTTPException(
            status_code=404, detail="No se encontraron fragmentos para el usuario.")

    logger.info(f"Found {len(user_fragments)} fragments for user ID: {request.user_id}.")

    # Unir los enlaces de audio y las transcripciones
    audio_links = [fragment["audio_url"] for fragment in user_fragments]
    transcriptions = " ".join(fragment["transcription"]
                              for fragment in user_fragments)

    logger.info(f"Collected {len(audio_links)} audio links and transcriptions for analysis.")

    # Realizar análisis textual utilizando OpenAI
    analysis_result = analyze_text(transcriptions)
    logger.info("Textual analysis completed.")

    # Realizar análisis de audio
    audio_analysis = analyze_audio(audio_links, transcriptions)
    logger.info("Audio analysis completed.")

    # Retornar resultados del análisis
    result = {
        "conversation_id": request.conversation_id,
        "user_id": request.user_id,
        "audio_links": audio_links,
        "textual_analysis": json.loads(analysis_result["choices"][0]["message"]["content"]),
        "audio_analysis": json.loads(audio_analysis)
    }

    logger.info(f"Analysis result for conversation ID: {request.conversation_id} and user ID: {request.user_id} returned successfully.")
    return generate_report(result)
