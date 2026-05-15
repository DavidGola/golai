import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.observability import flush_langfuse, initialize_sentry
from app.routers import auth, chat_config, games, health, users, user_games, conversations, proposals

os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)

initialize_sentry()

app = FastAPI(title="GolAi API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, tags=["users"])
app.include_router(user_games.router, tags=["user_games"])
app.include_router(conversations.router, tags=["conversations"])
app.include_router(chat_config.router)
app.include_router(proposals.router)
app.include_router(games.router)
app.include_router(health.router)

if settings.allow_anonymous_chat:
    from app.routers import anonymous_chat
    app.include_router(anonymous_chat.router)



@app.on_event("shutdown")
def shutdown_observability():
    flush_langfuse()
