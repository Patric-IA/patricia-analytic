import os
import tempfile
import requests
import boto3
import uuid
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from fastapi import HTTPException
from app.config import BUCKET_NAME, MONGO_URI
from pydub import AudioSegment
import io
import librosa
import numpy as np
import logging


# Conexiones a S3 y MongoDB
s3 = boto3.resource('s3')
client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
db = client["patricia-database"]
conversations_collection = db["conversation"]

def upload_to_s3(file, filename):
    s3.Bucket(BUCKET_NAME).put_object(Key=filename, Body=file, ACL="public-read")
    return f"https://{BUCKET_NAME}.s3.amazonaws.com/{filename}"

def create_conversation(user_uuid_1, user_uuid_2):
    conversation_id = str(uuid.uuid4())
    conversation_data = {
        "conversation_id": conversation_id,
        "participants": [user_uuid_1, user_uuid_2],
        "fragments": []
    }
    result = conversations_collection.insert_one(conversation_data)
    return conversation_id, str(result.inserted_id)

def add_fragment_to_conversation(conversation_id, fragment):
    conversation = conversations_collection.find_one({"conversation_id": conversation_id})
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    
    conversations_collection.update_one(
        {"conversation_id": conversation_id},
        {"$push": {"fragments": fragment}}
    )


def collect_conversation_fragments(conversation_id):
    conversation = conversations_collection.find_one({"conversation_id": conversation_id})
    print(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    
    fragments = conversation.get("fragments", [])
    if not isinstance(fragments, list):
        raise HTTPException(status_code=400, detail="La conversación no contiene un arreglo válido de fragmentos.")

    return fragments

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_text(transcriptions):
    """
    Realiza un análisis textual de la transcripción usando la API de OpenAI.
    """
    logger.info("Iniciando análisis textual de la transcripción.")
    prompt = (
        "You are an AI tool designed to automate language learning processes. "
        "Please analyze the audio corresponding to the context phrase: \"{context_phrase}\" and provide a detailed JSON response that includes evaluations for the following aspects: "
        "1. **Pronunciation**: Rate from 1 to 5, where 5 indicates clear and accurate pronunciation. "
        "2. **Errors**: Identify and list any significant language errors, rated from 1 to 5, where 5 indicates no errors. "
        "3. **Fluency**: Rate from 1 to 5, where 5 indicates smooth and natural speech. "
        "Please ensure the JSON object follows this structure:\n"
        "{\n"
        "  \"pronunciation\": <rating>,\n"
        "  \"errors\": <rating>,\n"
        "  \"fluency\": <rating>,\n"
        "  \"error_details\": [\"error1\", \"error2\", ...]\n"
        "}\n"
        "Make sure to provide feedback that is actionable and constructive for learning improvement."
    )

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
    )

    if response.status_code != 200:
        logger.error(f"Error al analizar la conversación. Código de estado: {response.status_code}")
        raise HTTPException(status_code=response.status_code, detail="Error al analizar la conversación.")

    logger.info("Análisis textual completado con éxito.")
    return response.json()

def analyze_audio(audio_links):
    """
    Realiza un análisis de los archivos de audio descargándolos de S3 y
    usando librosa para obtener métricas básicas.
    """
    logger.info("Iniciando análisis de audio.")
    s3 = boto3.client('s3')
    combined_audio = AudioSegment.empty()

    # Descargar y combinar audios
    for link in audio_links:
        logger.info(f"Descargando audio desde: {link}")
        audio_key = link.split(f"https://{BUCKET_NAME}.s3.amazonaws.com/")[1]
        audio_obj = s3.get_object(Bucket=BUCKET_NAME, Key=audio_key)
        audio_data = io.BytesIO(audio_obj['Body'].read())
        segment = AudioSegment.from_file(audio_data)
        combined_audio += segment

    # Guardar el audio combinado para análisis
    audio_file_path = os.path.join(tempfile.gettempdir(), "combined_audio.wav")
    combined_audio.export(audio_file_path, format="wav")
    logger.info(f"Audio combinado guardado en: {audio_file_path}")

    # Extraer características de audio usando librosa
    y, sr = librosa.load(audio_file_path, sr=None)
    duration = librosa.get_duration(y=y, sr=sr)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    pitch = np.mean(librosa.yin(y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7')))

    logger.info("Análisis de audio completado con éxito.")
    # Retornar análisis de audio
    return {
        "duration_seconds": duration,
        "tempo": tempo,
        "average_pitch": pitch
    }
