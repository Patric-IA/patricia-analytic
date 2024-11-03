from fastapi import APIRouter
from app.models import ConversationCreateRequest
from app.services import create_conversation

router = APIRouter()

@router.post("/create-conversation")
async def create_conversation_route(request: ConversationCreateRequest):
    conversation_id, mongo_id = create_conversation(request.user_uuid_1, request.user_uuid_2)
    return {"conversation_id": conversation_id, "mongo_id": mongo_id}
