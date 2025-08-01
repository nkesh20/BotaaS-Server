from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.api.endpoints import auth, bots, flows, webhooks
from app.api.endpoints import broadcast_router
from app.core.config import settings
from app.db.session import create_tables, get_db
from app.models.user import User
from app.schemas.user import UserSchema, UserCreate


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    create_tables()

    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for Bot as a Service",
    version="0.1.0",
    lifespan=lifespan,
    openapi_url=f"{settings.API_PREFIX}/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],  # Specific origins
    allow_origin_regex=r"https://.*\.ngrok-free\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(bots.router, prefix="/api/v1", tags=["bots"])
app.include_router(flows.router, prefix="/api/v1", tags=["flows"])
app.include_router(webhooks.router, prefix="/api/v1", tags=["webhooks"])
app.include_router(broadcast_router, prefix="/api/v1", tags=["broadcast"])


@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME} API"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}





@app.get("/api/users/", response_model=List[UserSchema], tags=["users"])
def list_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieve all users.
    """
    users = User.get_users(db, skip=skip, limit=limit)
    return users


@app.get("/api/users/{user_id}", response_model=UserSchema, tags=["users"])
def get_user(user_id: int, db: Session = Depends(get_db)):
    """
    Get a specific user by ID.
    """
    db_user = User.get_by_id(db, user_id)
    if db_user is None:
        raise HTTPException(status_code=404)
    return db_user


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
