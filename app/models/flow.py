from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func
from typing import List, Optional, Dict, Any

from app.models.base import Base


class Flow(Base):
    __tablename__ = "flows"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("telegram_bots.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    # Flow definition stored as JSON
    nodes = Column(JSON, nullable=False, default=list)
    edges = Column(JSON, nullable=False, default=list)
    triggers = Column(JSON, nullable=True, default=list)
    variables = Column(JSON, nullable=True, default=dict)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    bot = relationship("TelegramBot", back_populates="flows")

    @classmethod
    def create(cls, db: Session, flow_data: Dict[str, Any]) -> "Flow":
        """Create a new flow."""
        db_flow = cls(**flow_data)
        db.add(db_flow)
        db.commit()
        db.refresh(db_flow)
        return db_flow

    @classmethod
    def get_by_id(cls, db: Session, flow_id: int) -> Optional["Flow"]:
        """Get flow by ID."""
        return db.query(cls).filter(cls.id == flow_id).first()

    @classmethod
    def get_by_bot_id(cls, db: Session, bot_id: int, skip: int = 0, limit: int = 100) -> List["Flow"]:
        """Get all flows for a specific bot."""
        return db.query(cls).filter(cls.bot_id == bot_id).offset(skip).limit(limit).all()

    @classmethod
    def get_active_flows(cls, db: Session, bot_id: int) -> List["Flow"]:
        """Get all active flows for a bot."""
        return db.query(cls).filter(
            cls.bot_id == bot_id,
            cls.is_active == True
        ).all()

    @classmethod
    def get_default_flow(cls, db: Session, bot_id: int) -> Optional["Flow"]:
        """Get the default flow for a bot."""
        return db.query(cls).filter(
            cls.bot_id == bot_id,
            cls.is_default == True,
            cls.is_active == True
        ).first()

    @classmethod
    def update(cls, db: Session, flow_id: int, flow_data: Dict[str, Any]) -> Optional["Flow"]:
        """Update a flow."""
        db_flow = db.query(cls).filter(cls.id == flow_id).first()
        if not db_flow:
            return None

        for key, value in flow_data.items():
            if hasattr(db_flow, key):
                setattr(db_flow, key, value)

        db.commit()
        db.refresh(db_flow)
        return db_flow

    @classmethod
    def delete(cls, db: Session, flow_id: int) -> bool:
        """Delete a flow."""
        db_flow = db.query(cls).filter(cls.id == flow_id).first()
        if not db_flow:
            return False

        db.delete(db_flow)
        db.commit()
        return True

    @classmethod
    def set_as_default(cls, db: Session, flow_id: int) -> Optional["Flow"]:
        """Set a flow as the default for its bot."""
        db_flow = db.query(cls).filter(cls.id == flow_id).first()
        if not db_flow:
            return None

        # Remove default flag from other flows of the same bot
        db.query(cls).filter(
            cls.bot_id == db_flow.bot_id,
            cls.id != flow_id
        ).update({"is_default": False})

        # Set this flow as default
        db_flow.is_default = True
        db.commit()
        db.refresh(db_flow)
        return db_flow

    def to_dict(self) -> Dict[str, Any]:
        """Convert flow to dictionary."""
        return {
            "id": self.id,
            "bot_id": self.bot_id,
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "nodes": self.nodes,
            "edges": self.edges,
            "triggers": self.triggers,
            "variables": self.variables,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
