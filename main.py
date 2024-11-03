from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from pydub import AudioSegment
import speech_recognition as sr
import io
import boto3
import dotenv
import uuid
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime
import threading
import os
from pydantic import BaseModel

dotenv.load_dotenv()

BUCKET_NAME = "patricia-agent"
app = FastAPI()

# S3 y MongoDB
s3 = boto3.resource('s3')
uri = os.getenv("MONGO_URI")
client = MongoClient(uri, server_api=ServerApi('1'))

try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
    db = client["patricia-database"]
    print("Created the database")
    conversations_collection = db["conversation"] 
    print("Created a collection in the database")
except Exception as e:
    print(e)



class ConversationCreateRequest(BaseModel):
    user_uuid_1: str
    user_uuid_2: str


def upload_to_s3(file, filename):
    s3.Bucket(BUCKET_NAME).put_object(Key=filename, Body=file, ACL="public-read")
    return f"https://{BUCKET_NAME}.s3.amazonaws.com/{filename}"

@app.post("/create-conversation")
async def create_conversation(request: ConversationCreateRequest):
    # Generar un ID único para la conversación
    conversation_id = str(uuid.uuid4())
    
    # Estructura del documento para insertar en MongoDB
    conversation_data = {
        "conversation_id": conversation_id,
        "participants": [request.user_uuid_1, request.user_uuid_2],
        "fragments": []
    }
    
    # Insertar la conversación en la colección de MongoDB
    result = conversations_collection.insert_one(conversation_data)

    return {"conversation_id": conversation_id, "mongo_id": str(result.inserted_id)}

@app.post("/audio-duration")
async def get_audio_duration(
    conversation_id: str = Form(...),
    speaker_id: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    file: UploadFile = File(...)
):
    type_file = file.filename.split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{type_file}"
    file_content = await file.read()

    # Subir a S3
    thread = threading.Thread(target=upload_to_s3, args=(file_content, unique_filename))
    thread.start()
    thread.join()  # Esperar a que el hilo termine para obtener la URL
    audio_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{unique_filename}"

    # Procesar audio
    audio = AudioSegment.from_file(io.BytesIO(file_content), format=type_file)
    wav_io = io.BytesIO()
    audio.export(wav_io, format="wav")
    wav_io.seek(0)

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(wav_io) as source:
            audio_data = recognizer.record(source)
            transcription = recognizer.recognize_google(audio_data, language="es-ES")
    except sr.UnknownValueError:
        transcription = "No se pudo transcribir el audio."
    except sr.RequestError as e:
        transcription = f"Error de servicio; {e}"
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Calcular duración
    duration_seconds = len(audio) / 1000

    # Crear el fragmento
    fragment = {
        "speaker": speaker_id,
        "start_time": start_time,
        "end_time": end_time,
        "transcription": transcription,
        "audio_url": audio_url
    }

    # Agregar el fragmento a la conversación en MongoDB
    conversation = conversations_collection.find_one({"conversation_id": conversation_id})
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    
    conversations_collection.update_one(
        {"conversation_id": conversation_id},
        {"$push": {"fragments": fragment}}
    )

    return {
        "conversation_id": conversation_id,
        "speaker": speaker_id,
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": duration_seconds,
        "transcription": transcription,
        "audio_url": audio_url
    }
