from pydantic import BaseModel, Field
from typing import List, Dict

class ConversationCreateRequest(BaseModel):
    user_uuid_1: str
    user_uuid_2: str

class ConversationAnalysisRequest(BaseModel):
    user_id: str
    conversation_id: str

class UserModel(BaseModel):
    date_of_birth: str  # o Date si prefieres manejarlo como un objeto de fecha

class PersonModel(BaseModel):
    user: UserModel
    interests: List[str]
    hobbies: List[str]
    user_values: List[str]
    learning_preferences: str
    digital_behavior: str
    conversation_topics: List[str]
