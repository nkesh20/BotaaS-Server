from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.db.session import get_db
from app.services.broadcast_manager import BroadcastManager

router = APIRouter()
broadcast_manager = BroadcastManager()

class BroadcastRequest(BaseModel):
    bot_id: int
    text: str
    scheduled_time: Optional[datetime] = None
    parse_mode: Optional[str] = None

@router.post("/broadcast/")
async def trigger_broadcast(request: BroadcastRequest, db: Session = Depends(get_db)):
    try:
        await broadcast_manager.schedule_broadcast(
            db=db,
            bot_id=request.bot_id,
            text=request.text,
            scheduled_time=request.scheduled_time,
            parse_mode=request.parse_mode
        )
        return {"status": "scheduled" if request.scheduled_time else "started"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 