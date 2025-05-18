import os
import uuid
import logging
from typing import List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from datetime import datetime
from passlib.context import CryptContext

from prisma_client import Prisma, Json
from dotenv import load_dotenv, find_dotenv

# Load environment variables
load_dotenv(find_dotenv())

# Settings
class Settings(BaseSettings):
    database_url: str = Field(..., env="DATABASE_URL")
    log_level: str     = Field("INFO",     env="LOG_LEVEL")

settings = Settings()

# Logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Initialize Prisma client
prisma = Prisma()

# Lifespan context for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    await prisma.connect()
    logger.info("Prisma connected.")
    yield
    await prisma.disconnect()
    logger.info("Prisma disconnected.")

# FastAPI app
app = FastAPI(
    title="Search Agent API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-Session-ID", "X-User-ID", "Content-Type"],
)

# ---------------------- Models ----------------------

class ChatRequest(BaseModel):
    message:     str
    session_id:  Optional[str] = Body(None, alias="session_id")
    user_id:     Optional[str] = Body(None, alias="user_id")

    class Config:
        allow_population_by_field_name = True

class UserModel(BaseModel):
    email:           str
    password:        str
    isSubscribed:    bool           = False
    subscription:    Optional[dict] = {}
    freePlanUsage:   Optional[dict] = {}
    role:            str            = "admin"
    agentSessions:   List[dict]     = []
    createdAt:       datetime       = Field(default_factory=datetime.utcnow)
    updatedAt:       datetime       = Field(default_factory=datetime.utcnow)
    paymentStatus:   str            = "inactive"
    plan:            str            = "free"
    notifications:   List[dict]     = []

class UserUpdateModel(BaseModel):
    email:           Optional[str]
    password:        Optional[str]
    isSubscribed:    Optional[bool]
    subscription:    Optional[dict]
    freePlanUsage:   Optional[dict]
    role:            Optional[str]
    paymentStatus:   Optional[str]
    plan:            Optional[str]
    agentSessions:   Optional[List[dict]]
    notifications:   Optional[List[dict]]

class LoginRequest(BaseModel):
    email:    str
    password: str

# ---------------------- Chat Endpoints ----------------------

@app.post("/chat")
async def handle_chat_message(chat_request: ChatRequest):
    # 1) Verify provided user_id exists
    user_id = chat_request.user_id
    if user_id:
        if not await prisma.user.find_unique(where={"id": user_id}):
            user_id = None

    # 2) Auto-create anon user if none
    if not user_id:
        anon_email = f"anon_{uuid.uuid4().hex}@example.com"
        anon_password = pwd_context.hash(uuid.uuid4().hex)
        new_user = await prisma.user.create(
            data={"email": anon_email, "password": anon_password}
        )
        user_id = new_user.id
        logger.info(f"Auto-created anon user: {user_id}")

    # 3) Reuse last session if no session_id supplied
    session_id = chat_request.session_id
    if not session_id:
        last = await prisma.chatsession.find_first(
            where={"user_id": user_id},
            order={"created_at": "desc"}
        )
        session_id = last.session_id if last else str(uuid.uuid4())

    message = chat_request.message

    # 4) Fetch or create session
    session = await prisma.chatsession.find_unique(where={"session_id": session_id})
    
    if not session:
        session = await prisma.chatsession.create(
            data={
                "session_id": session_id,
                "user_id":    user_id,
                "history":    Json([{"role": "system", "content": "I am Deep Search Agent!"}]),
            }
        )
        logger.info(f"Created session: {session_id}")

        # Push notification
        try:
            user_rec = await prisma.user.find_unique(where={"id": user_id})
            notifs = user_rec.notifications or []
            await prisma.user.update(
                where={"id": user_id},
                data={"notifications": Json(notifs + [{"user_id": user_id}])}
            )
            logger.info(f"Notification added for user {user_id}")
        except Exception as e:
            logger.error(f"Notif failed for {user_id}: {e}", exc_info=True)
    else:
        if session.user_id != user_id:
            await prisma.chatsession.update(
                where={"id": session.id},
                data={"user_id": user_id}
            )
        session.history = session.history or []

    # 5) Append user message
    history = session.history
    history.append({"role": "user", "content": message})

    try:
        # 6) Invoke agent
        from agent_core import agent, run_config, Runner
        result = Runner.run_streamed(agent, input=history, run_config=run_config)
        async for _ in result.stream_events():
            pass
        agent_reply = result.final_output

        # 7) Append assistant reply & update session
        history.append({"role": "assistant", "content": agent_reply})
        await prisma.chatsession.update(
            where={"id": session.id},
            data={"history": Json(history)}
        )

        # 8) Return response
        return JSONResponse(
            content={
                "statusCode": status.HTTP_200_OK,
                "success": True,
                "message": "Response processed successfully.",
                "data": {
                    "sessionId": session_id,
                    "userId":    user_id,
                    "prompt":    message,
                    "reply":     agent_reply
                }
            },
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Error in session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------- Session Endpoints ----------------------

@app.get("/sessions/{session_id}")
async def get_session_history(session_id: str):
    session = await prisma.chatsession.find_unique(where={"session_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"sessionId": session_id, "history": session.history}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    deleted_count = await prisma.chatsession.delete_many(where={"session_id": session_id})
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True, "sessionId": session_id}


@app.get("/users/{user_id}/sessions")
async def get_sessions_by_user(user_id: str):
    sessions = await prisma.chatsession.find_many(
        where={"user_id": user_id}
    )
    return {
        "userId": user_id,
        "sessions": [
            {"sessionId": s.session_id, "history": s.history}
            for s in sessions
        ]
    }


@app.delete("/users/{user_id}/sessions")
async def delete_sessions_by_user(user_id: str):
    deleted_count = await prisma.chatsession.delete_many(where={"user_id": user_id})
    return {"deletedCount": deleted_count, "userId": user_id}




@app.get("/chathistories")
async def get_all_chathistories():
    sessions = await prisma.chatsession.find_many()
    return {
        "chathistories": [
            {"sessionId": s.session_id, "history": s.history}
            for s in sessions
        ]
    }

# ---------------------- User Endpoints ----------------------

@app.post("/users", status_code=201)
async def create_user(user: UserModel):
    data = user.dict(exclude={"agentSessions", "notifications", "createdAt", "updatedAt"})
    data["password"] = pwd_context.hash(user.password)
    # wrap JSON fields
    data["subscription"]  = Json(data.get("subscription", {}))
    data["freePlanUsage"] = Json(data.get("freePlanUsage", {}))
    new = await prisma.user.create(data=data)
    return {"status": "created", "userId": new.id}


@app.get("/users/{user_id}")
async def get_user(user_id: str):
    u = await prisma.user.find_unique(where={"id": user_id})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    result = {
        "userId":       u.id,
        "email":        u.email,
        "isSubscribed": u.isSubscribed,
        "subscription": u.subscription,
        "freePlanUsage":u.freePlanUsage,
        "role":         u.role,
        "agentSessions":u.agentSessions,
        "notifications":u.notifications,
        "createdAt":    u.createdAt,
        "updatedAt":    u.updatedAt,
        "paymentStatus":u.paymentStatus,
        "plan":         u.plan,
    }
    return result



@app.put("/users/{user_id}")
async def update_user(
    user_id: str,
    up: dict = Body(..., description="Fields to update on the user")
):
    # Define which top‐level fields are valid on the User model
    valid_fields = {
        "email",
        "password",
        "isSubscribed",
        "subscription",
        "freePlanUsage",
        "role",
        "paymentStatus",
        "plan",
        "agentSessions",
        "notifications",
    }

    # Build a clean dict of only the valid fields
    data: dict[str, Any] = {}
    for key, value in up.items():
        if key not in valid_fields:
            # skip any unknown keys rather than trying to write them directly
            continue

        if key == "password":
            # hash new passwords
            data["password"] = pwd_context.hash(value)
        elif key in {"subscription", "freePlanUsage", "agentSessions", "notifications"}:
            # wrap JSON/array fields
            data[key] = Json(value)
        else:
            # primitive scalar fields
            data[key] = value

    # Always update the timestamp
    data["updatedAt"] = datetime.utcnow()

    # Perform the update
    updated_count = await prisma.user.update_many(
        where={"id": user_id},
        data=data
    )
    if updated_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"status": "updated", "userId": user_id}




@app.delete("/users/{user_id}")
async def delete_user(user_id: str):
    # delete_many returns the number of records deleted
    deleted_count = await prisma.user.delete_many(where={"id": user_id})
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"deleted": True, "userId": user_id}




@app.post("/login")
async def login(req: LoginRequest):
    u = await prisma.user.find_unique(where={"email": req.email})
    if not u or not pwd_context.verify(req.password, u.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"status": "ok", "userId": u.id}
