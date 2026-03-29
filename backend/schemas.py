from pydantic import BaseModel
from typing import Optional


class JobCreate(BaseModel):
    title: str
    description: Optional[str] = None
    task_type: str
    input_payload: dict = {}
    user_id: Optional[str] = None
    priority: int = 1
    reward_amount: float = 0.00
    requires_validation: bool = True


class TaskClaim(BaseModel):
    worker_node_id: str
    task_types: Optional[list[str]] = None  # filter to only claim matching types
    worker_tier: int = 1


class WorkerRegister(BaseModel):
    node_name: str
    capabilities: Optional[dict] = None  # hardware info (ram_gb, cores, has_gpu, tier)


class TaskComplete(BaseModel):
    result_text: Optional[str] = None
    result_payload: Optional[dict] = None
    execution_time_seconds: Optional[float] = None


class WorkerHeartbeat(BaseModel):
    worker_node_id: str
