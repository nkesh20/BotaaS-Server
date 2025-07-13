# app/api/endpoints/flows.py
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.flow import Flow
from app.models.user import User
from app.schemas.flow import FlowResponse, FlowCreate, FlowUpdate, FlowExecutionContext
from app.services.flow_engine import FlowEngine

router = APIRouter(prefix="/flows", tags=["flows"])


@router.get("/{bot_id}", response_model=List[FlowResponse])
def get_bot_flows(
        bot_id: int,
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Get all flows for a specific bot.
    """
    flows = Flow.get_by_bot_id(db, bot_id=bot_id, skip=skip, limit=limit)
    
    # If no flows exist, create a default welcome flow
    if not flows:
        default_flow_data = {
            "bot_id": bot_id,
            "name": "Welcome Flow",
            "description": "Default welcome flow for new users",
            "is_active": True,
            "is_default": True,
            "nodes": [
                {
                    "id": "start",
                    "label": "Start",
                    "data": {"type": "start"},
                    "position": {"x": 100, "y": 100}
                },
                {
                    "id": "welcome_message",
                    "label": "Welcome Message",
                    "data": {
                        "type": "message",
                        "content": "Hello! Welcome to our bot. How can I help you today?"
                    },
                    "position": {"x": 300, "y": 100}
                }
            ],
            "edges": [
                {
                    "id": "start_to_welcome",
                    "source": "start",
                    "target": "welcome_message",
                    "label": "Next"
                }
            ],
            "triggers": [],
            "variables": {}
        }
        
        try:
            default_flow = Flow.create(db, default_flow_data)
            flows = [default_flow]
        except Exception as e:
            print(f"Error creating default flow: {e}")
    
    return flows


@router.get("/{bot_id}/{flow_id}", response_model=FlowResponse)
def get_flow(
        bot_id: int,
        flow_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Get a specific flow by ID.
    """
    flow = Flow.get_by_id(db, flow_id=flow_id)
    if not flow or flow.bot_id != bot_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found"
        )
    
    # Ensure the flow has the required structure
    if not flow.nodes:
        flow.nodes = []
    if not flow.edges:
        flow.edges = []
    
    return flow


@router.post("/{bot_id}", response_model=FlowResponse)
def create_flow(
        bot_id: int,
        flow_data: FlowCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Create a new flow for a bot.
    """
    # Verify bot exists and user has access
    # You might want to add bot ownership check here

    flow_data_dict = flow_data.model_dump()
    flow_data_dict["bot_id"] = bot_id

    flow = Flow.create(db, flow_data=flow_data_dict)
    return flow


@router.put("/{bot_id}/{flow_id}", response_model=FlowResponse)
def update_flow(
        bot_id: int,
        flow_id: int,
        flow_data: FlowUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Update an existing flow.
    """
    flow = Flow.get_by_id(db, flow_id=flow_id)
    if not flow or flow.bot_id != bot_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found"
        )

    updated_flow = Flow.update(db, flow_id=flow_id, flow_data=flow_data.model_dump(exclude_unset=True))
    return updated_flow


@router.delete("/{bot_id}/{flow_id}")
def delete_flow(
        bot_id: int,
        flow_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Delete a flow.
    """
    flow = Flow.get_by_id(db, flow_id=flow_id)
    if not flow or flow.bot_id != bot_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found"
        )

    Flow.delete(db, flow_id=flow_id)
    return {"message": "Flow deleted successfully"}


@router.post("/{bot_id}/{flow_id}/activate")
def activate_flow(
        bot_id: int,
        flow_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Activate a flow (set as active).
    """
    flow = Flow.get_by_id(db, flow_id=flow_id)
    if not flow or flow.bot_id != bot_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found"
        )

    updated_flow = Flow.update(db, flow_id=flow_id, flow_data={"is_active": True})
    return {"message": "Flow activated successfully", "flow": updated_flow}


@router.post("/{bot_id}/{flow_id}/deactivate")
def deactivate_flow(
        bot_id: int,
        flow_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Deactivate a flow.
    """
    flow = Flow.get_by_id(db, flow_id=flow_id)
    if not flow or flow.bot_id != bot_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found"
        )

    updated_flow = Flow.update(db, flow_id=flow_id, flow_data={"is_active": False})
    return {"message": "Flow deactivated successfully", "flow": updated_flow}


@router.post("/{bot_id}/{flow_id}/set-default")
def set_flow_as_default(
        bot_id: int,
        flow_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Set a flow as the default flow for a bot.
    """
    flow = Flow.get_by_id(db, flow_id=flow_id)
    if not flow or flow.bot_id != bot_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found"
        )

    updated_flow = Flow.set_as_default(db, flow_id=flow_id)
    return {"message": "Flow set as default successfully", "flow": updated_flow}


@router.post("/{bot_id}/{flow_id}/execute")
async def execute_flow(
        bot_id: int,
        flow_id: int,
        message: str,
        user_id: str,
        session_id: str = None,
        db: Session = Depends(get_db)
):
    """
    Execute a flow with a user message.
    """
    if not session_id:
        session_id = f"session_{user_id}_{int(datetime.now().timestamp())}"

    # Create execution context
    context = FlowExecutionContext(
        user_id=user_id,
        session_id=session_id,
        variables={}
    )

    # Execute flow
    engine = FlowEngine(db)
    try:
        result = await engine.execute_flow(flow_id, message, context)
        return result
    finally:
        await engine.close()


@router.post("/{bot_id}/webhook")
async def webhook_handler(
        bot_id: int,
        payload: dict,
        db: Session = Depends(get_db)
):
    """
    Handle incoming webhooks for bots.
    """
    # Extract message and user info from payload
    user_id = payload.get("user_id")
    message = payload.get("message")

    if not user_id or not message:
        raise HTTPException(
            status_code=400,
            detail="user_id and message are required"
        )

    # Find default flow for the bot
    default_flow = Flow.get_default_flow(db, bot_id)
    if not default_flow:
        raise HTTPException(
            status_code=404,
            detail="No default flow found for bot"
        )

    # Execute flow
    session_id = payload.get("session_id", f"session_{user_id}_{int(datetime.now().timestamp())}")
    context = FlowExecutionContext(
        user_id=user_id,
        session_id=session_id,
        variables=payload.get("variables", {})
    )

    engine = FlowEngine(db)
    try:
        result = await engine.execute_flow(default_flow.id, message, context)
        return {
            "success": result.success,
            "response": result.response_message,
            "quick_replies": result.quick_replies,
            "session_id": session_id
        }
    finally:
        await engine.close()
