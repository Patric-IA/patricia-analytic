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
import json
from openai import OpenAI
from datetime import datetime
import re

# Conexiones a S3 y MongoDB
s3 = boto3.resource('s3')
client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
db = client["patricia-database"]
conversations_collection = db["conversation"]
client = OpenAI()

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
    
    transcription = "#".join(transcriptions) 

    logger.info("Iniciando análisis textual de la transcripción.")
    prompt = f"""
    You are an English language evaluator. Analyze the following English sentences separated by the '#' character:

    {transcription}

    Please provide your analysis in a valid JSON format without any extra characters or quotes. The JSON should include:
    1. An "analysis" object with numerical scores from 1 to 10 for each of the following factors:
    - "grammar": Assessment of grammatical structure.
    - "vocabulary": Richness and accuracy of the vocabulary used.
    - "fluency": Level of fluency in speaking or writing.
    - "coherence": Logic and coherence in the construction of the sentences.
    - "style": Appropriateness of style based on context (if relevant).

    2. A "critical_feedback" string providing constructive feedback on each factor.

    Your response should be structured like this:

    {{
        "analysis": {{
            "grammar": <score>,
            "vocabulary": <score>,
            "fluency": <score>,
            "coherence": <score>,
            "style": <score>
        }},
        "critical_feedback": "<feedback>"
    }}
    Make sure to return only the JSON object, without additional formatting or text.
    """

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
    )

    if response.status_code != 200:
        logger.error(f"Error al analizar la conversación. Código de estado: {response.status_code}")
        raise HTTPException(status_code=response.status_code, detail="Error al analizar la conversación.")

    logger.info("Análisis textual completado con éxito.")

    # Intenta convertir la respuesta en JSON
    try:
        response_json = response.json()  # Esto debería ser un JSON ya
        # Si la respuesta tiene el contenido textual como un string JSON, puedes parsearlo
        if isinstance(response_json, str):
            response_json = json.loads(response_json)  # Convierte a objeto JSON

        return response_json
    except json.JSONDecodeError:
        logger.error("Error al decodificar el JSON de la respuesta.")
        raise HTTPException(status_code=500, detail="Error al procesar el análisis textual.")


def analyze_audio(audio_links, transcriptions):
    """
    Realiza un análisis de los archivos de audio descargándolos de S3 y
    usando librosa para obtener métricas avanzadas.
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
    rms = np.mean(librosa.feature.rms(y=y))
    zcr = np.mean(librosa.feature.zero_crossing_rate(y))
    spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
    spectral_bandwidth = np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr))
    spectral_contrast = np.mean(librosa.feature.spectral_contrast(y=y, sr=sr))
    spectral_flatness = np.mean(librosa.feature.spectral_flatness(y=y))
    mfccs = np.mean(librosa.feature.mfcc(y=y, sr=sr), axis=1)

    logger.info("Análisis de audio completado con éxito.")
    def convert_to_serializable(obj):
        if isinstance(obj, (np.ndarray, list)):
            return [float(x) for x in obj]
        elif isinstance(obj, (np.float32, np.float64)):
            return float(obj)
        return obj

    # Crear el diccionario con los resultados
    results = {
        "tempo": convert_to_serializable(tempo),
        "average_pitch": convert_to_serializable(pitch),
        "rms": convert_to_serializable(rms),
        "zero_crossing_rate": convert_to_serializable(zcr),
        "spectral_centroid": convert_to_serializable(spectral_centroid),
        "spectral_bandwidth": convert_to_serializable(spectral_bandwidth),
        "spectral_contrast": convert_to_serializable(spectral_contrast),
        "spectral_flatness": convert_to_serializable(spectral_flatness),
        "mfccs": convert_to_serializable(mfccs)  # Convertir MFCCs
    }

    return json.dumps(results)



def getClassesMongoDB():
    classes = db["courses"]
    return classes.find({})

def mapClasses():
    class_data = getClassesMongoDB()
    mapped_classes = []

    for class_entry in class_data:
        # Mapea los datos de cada clase
        mapped_entry = {
            "_id": str(class_entry["_id"]),
            "name": class_entry["name"],
            "url": class_entry["url"],
            "level": class_entry["level"],
            "summary": class_entry["summary"],
            "classes": [],
            "video_titles": []
        }

        # Mapea las clases individuales
        for video in class_entry.get("classes", []):
            video_entry = {
                "url": video["url"],
                "name": video["name"],
                "summary": video["summary"]
            }
            mapped_entry["classes"].append(video_entry)
            mapped_entry["video_titles"].append(video["name"])

        mapped_classes.append(mapped_entry)

    return json.dumps(mapped_classes, ensure_ascii=False, indent=4)


def generate_report(conversation_data):
    classesMap = mapClasses()

    prompt = f"""
    Based on the following conversation data:
    {conversation_data}

    COURSES: 
    {classesMap}

    Please generate a detailed feedback report in JSON format that includes the following sections, ALL THE FEEDBACK HAS TO BE IN SPANISH:

    {{
        "feedback": "Provide a comprehensive evaluation of the conversational performance. Highlight strengths, such as effective use of vocabulary or clarity in pronunciation, as well as weaknesses, such as areas needing improvement. Use specific examples from the conversation data to support your points and offer constructive suggestions for enhancement.",
        
        "metrics": {{
            "grammar_score": "Rate from 1 to 5 based on grammatical accuracy, with specific examples to justify the rating.",
            "vocabulary": "Rate from 1 to 5 based on the range and appropriateness of vocabulary used in the conversation. Provide suggestions for improvement where applicable.",
            "pronunciation": "Rate from 1 to 5 based on the clarity and accuracy of pronunciation. Include tips for practice if needed.",
            "fluency": "Rate from 1 to 5 based on the flow and pace of speech, noting any hesitations or disruptions.",
            "coherence": "Rate from 1 to 5 based on the logical flow and organization of ideas presented in the conversation. Suggest ways to enhance coherence.",
            "style": "Rate from 1 to 5 based on the appropriateness of the style for the context. Discuss any adjustments that could improve effectiveness.",
        }},
        
        "recommended_courses": [
            {{
                "link": "URL to recommended course",
                "justification": "Explain why this course is recommended based on the student's performance and identified areas for improvement."
            }}
        ]
    }}

    Ensure that the output is structured, clear, and actionable, adhering strictly to the specified JSON format.
    """
    
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
    )


    if response.status_code == 200:
        json_response_str = response.json()['choices'][0]['message']['content']
        
        cleaned_response_str = json_response_str.replace("```json\n", "").replace("```", "").strip()

        try:
            json_response = json.loads(cleaned_response_str)
            return json_response
        except json.JSONDecodeError as e:
            raise Exception(f"Error decoding JSON: {e}")
    else:
        raise Exception(f"Error in request: {response.status_code}, {response.text}")


def call_openai_api(person1, person2, data_analysis):
    prompt = f"""
      **Objective**: To connect individuals based on their interests and compatibility for the purpose of learning English and practicing together.

      **Data Analysis**:
      - **Age Difference**: {data_analysis['age_difference']} years
      - **Common Interests Count**: {data_analysis['interest_common']}
      - **Common Hobbies Count**: {data_analysis['hobbies_common']}
      - **Learning Preferences Match**: {data_analysis['learning_preferences_match']}
      - **User Values Match**: {data_analysis['user_values_match']}
      - **Digital Behavior Match**: {data_analysis['digital_behavior_match']}
      - **Common Conversation Topics Count**: {data_analysis['conversation_topics_common']}

      **Detailed Criteria**:
      - **Depth of Common Interests**: Assess the significance of common interests. Are they aligned with both individuals' goals?
      - **Hobbies' Impact on Compatibility**: Evaluate how shared hobbies can facilitate bonding and conversation.
      - **Learning Preferences**: Consider how closely the individuals' preferred learning styles complement each other.
      - **Values in Relationships**: Analyze how aligned values may contribute to deeper understanding and conflict resolution.
      - **Digital Behavior Compatibility**: Examine how similar digital behaviors can affect their interaction frequency and comfort.
      - **Conversation Topics Alignment**: Explore how well the common conversation topics can foster engaging discussions.

      **Compatibility Evaluation**:
      - Evaluate the compatibility considering the above factors and their significance for effective communication without awkward silences.
      **Expected Response**: Provide a compatibility score from 0 to 1, considering both positive and negative influences on the score. Return only the final score without explanations o textos adicionales.
    """

    print("Prompt:", prompt)  # Debugging: Print the prompt to check the input for la API

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    result = completion.choices[0].message.content

    match = re.search(r"(\b0(?:\.\d+)?|1(?:\.0)?)", result)
    score = float(match.group(0)) if match else None

    return score

def analyze_data(person1, person2):
    # Convertir las fechas de nacimiento de cadena a objeto datetime
    dob1 = datetime.strptime(person1.user.date_of_birth, '%Y-%m-%d')
    dob2 = datetime.strptime(person2.user.date_of_birth, '%Y-%m-%d')

    analysis = {
        "age_difference": abs((dob1 - dob2).days // 365),  # Calcula la diferencia de edad en años
        "interest_common": len(set(person1.interests).intersection(set(person2.interests))),
        "hobbies_common": len(set(person1.hobbies).intersection(set(person2.hobbies))),
        "learning_preferences_match": person1.learning_preferences == person2.learning_preferences,
        "user_values_match": person1.user_values == person2.user_values,
        "digital_behavior_match": person1.digital_behavior == person2.digital_behavior,
        "conversation_topics_common": len(set(person1.conversation_topics).intersection(set(person2.conversation_topics)))
    }
    return analysis

def evaluate_compatibility(person1, person2):
    data_analysis = analyze_data(person1, person2)

    # Llamar a la API de OpenAI para obtener el puntaje de compatibilidad
    compatibility_score = call_openai_api(person1, person2, data_analysis)

    return compatibility_score
