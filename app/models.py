from pydantic import BaseModel

class ConversationCreateRequest(BaseModel):
    user_uuid_1: str
    user_uuid_2: str

class ConversationAnalysisRequest(BaseModel):
    user_id: str
    conversation_id: str
