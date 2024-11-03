from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from app.services import upload_to_s3, add_fragment_to_conversation
from pydub import AudioSegment
import io
import uuid
import speech_recognition as sr

router = APIRouter()

@router.post("/record-conversation")
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
    audio_url = upload_to_s3(file_content, unique_filename)

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

    add_fragment_to_conversation(conversation_id, fragment)

    return {
        "conversation_id": conversation_id,
        "speaker": speaker_id,
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": duration_seconds,
        "transcription": transcription,
        "audio_url": audio_url
    }
