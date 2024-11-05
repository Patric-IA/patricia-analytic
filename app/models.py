from pydantic import BaseModel

class ConversationCreateRequest(BaseModel):
    user_uuid_1: str
    user_uuid_2: str

class ConversationAnalysisRequest(BaseModel):
    user_id: str
    conversation_id: str


class User(BaseModel):
    date_of_birth: str 

class Person(BaseModel):
    user: User
    interests: List[str]
    hobbies: List[str]
    user_values: List[str]
    learning_preferences: str
    digital_behavior: str
    conversation_topics: List[str]
