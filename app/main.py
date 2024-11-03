from fastapi import FastAPI
from app.routes.conversation import router as conversation_router
from app.routes.audio import router as audio_router
from app.routes.analysis import router as analysis_router

app = FastAPI()

app.include_router(conversation_router)
app.include_router(audio_router)
app.include_router(analysis_router)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Patricia Agent API!"}
