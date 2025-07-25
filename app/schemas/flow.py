from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class FlowNodeData(BaseModel):
    type: str = Field(..., pattern="^(start|message|condition|action|webhook|input|end)$")
    content: Optional[str] = None
    quick_replies: Optional[List[str]] = None
    webhook_url: Optional[str] = None
    method: Optional[str] = "POST"
    headers: Optional[str] = "{}"
    request_body: Optional[str] = "{}"
    condition_type: Optional[str] = None
    condition_value: Optional[str] = None
    action_type: Optional[str] = None
    action_params: Optional[str] = "{}"
    input_type: Optional[str] = "text"
    variable_name: Optional[str] = None
    validation_pattern: Optional[str] = None
    delay: Optional[int] = 0
    retry_count: Optional[int] = 0
    tags: Optional[List[str]] = None
    conditions: Optional[List[Any]] = None
    webhookUrl: Optional[str] = None
    color: Optional[str] = None

    class Config:
        extra = "allow"  # Allow extra fields like color


class FlowNode(BaseModel):
    id: str
    label: str
    data: FlowNodeData
    position: Optional[Dict[str, float]] = Field(default={"x": 0, "y": 0})
    meta: Optional[Dict[str, Any]] = None
    dimension: Optional[Dict[str, Any]] = None
    transform: Optional[str] = None

    class Config:
        extra = "allow"  # Allow extra fields from ngx-graph


class FlowEdge(BaseModel):
    id: str
    source: str
    target: str
    label: Optional[str] = None
    condition: Optional[str] = None

    class Config:
        extra = "allow"  # Allow extra fields from ngx-graph


class FlowTrigger(BaseModel):
    id: str
    type: str = Field(..., pattern="^(keyword|intent|event|webhook)$")
    value: str
    is_active: bool = True


class FlowVariable(BaseModel):
    name: str
    type: str = Field(..., pattern="^(string|number|boolean|object)$")
    default_value: Optional[Any] = None
    description: Optional[str] = None


class FlowBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: bool = True
    is_default: bool = False
    nodes: List[FlowNode] = Field(default_factory=list)
    edges: List[FlowEdge] = Field(default_factory=list)
    triggers: List[FlowTrigger] = Field(default_factory=list)
    variables: Dict[str, Any] = Field(default_factory=dict)  # Changed from FlowVariable to Any


class FlowCreate(FlowBase):
    """Schema for creating a new flow."""
    pass


class FlowUpdate(BaseModel):
    """Schema for updating a flow. All fields are optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    nodes: Optional[List[FlowNode]] = None
    edges: Optional[List[FlowEdge]] = None
    triggers: Optional[List[FlowTrigger]] = None
    variables: Optional[Dict[str, Any]] = None


class FlowResponse(FlowBase):
    """Schema for flow responses."""
    id: int
    bot_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FlowExecutionContext(BaseModel):
    """Context for flow execution."""
    bot_id: str
    user_id: str
    session_id: str
    current_node_id: Optional[str] = None
    variables: Dict[str, Any] = Field(default_factory=dict)
    history: List[Dict[str, Any]] = Field(default_factory=list)


class FlowExecutionResult(BaseModel):
    """Result of flow execution."""
    success: bool
    next_node_id: Optional[str] = None
    output: Optional[str] = None
    response_message: Optional[str] = None
    quick_replies: Optional[List[str]] = None
    variables_updated: Dict[str, Any] = Field(default_factory=dict)
    actions_performed: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


class WebhookPayload(BaseModel):
    """Payload structure for webhook calls."""
    user_id: str
    session_id: str
    message: str
    variables: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    flow_id: int
    node_id: str
