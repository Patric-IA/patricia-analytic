from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.conversation import router as conversation_router
from app.routes.audio import router as audio_router
from app.routes.analysis import router as analysis_router
from app.routes.matchmaking import router as matchmaking_router

app = FastAPI()

# Habilita CORS para permitir solicitudes de cualquier origen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversation_router)
app.include_router(audio_router)
app.include_router(analysis_router)
app.include_router(matchmaking_router)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Patricia Agent API!"}
