import os
import json
import time
import uuid
import logging

from fastapi import APIRouter, BackgroundTasks

from .models import EnrichmentInput, EnrichmentAggregatorInput
from .redis_client import redis_client, TASK_RESULT_TTL
from .services import (
    get_redis_data,
    filter_low_confidence_contacts,
    process_enqueue_enrichment,
    process_enrichment_aggregation,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@router.post("/enqueue_enrichment")
async def enqueue_enrichment(input_data: EnrichmentInput, background_tasks: BackgroundTasks):
    """Enqueue an enrichment run that will find HR contacts for each company."""
    task_id = str(uuid.uuid4())
    webhook_url = os.getenv("WEBHOOK_URL", "")
    
    redis_data = {
        "task_id": task_id,
        "status": "pending",
        "create_time": time.time(),
        "numTasks": len(input_data.formData),
        "numTasksCompleted": 0,
        "results": [],
        "errors": [],
        "webhookUrl": webhook_url,
    }
    
    redis_client.setex(f"task:{task_id}", TASK_RESULT_TTL, json.dumps(redis_data))
    logger.info(f"Task task:{task_id} created in redis", extra={"task_id": task_id})
    
    background_tasks.add_task(process_enqueue_enrichment, input_data, task_id)
    
    return {"task_id": task_id, "status": "processing", "numCompanies": len(input_data.formData)}


@router.post("/aggregate_enrichment")
async def aggregate_enrichment(input_data: EnrichmentAggregatorInput, background_tasks: BackgroundTasks):
    """Aggregator endpoint called by workers when they complete processing a company."""
    background_tasks.add_task(process_enrichment_aggregation, input_data)
    return {"status": "processing"}


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """Get the current status of an enrichment task."""
    redis_data = get_redis_data(task_id)
    return {
        "task_id": redis_data.task_id,
        "status": redis_data.status,
        "numTasks": redis_data.numTasks,
        "numTasksCompleted": redis_data.numTasksCompleted,
        "create_time": redis_data.create_time,
    }


@router.get("/task/{task_id}/results")
async def get_task_results(task_id: str):
    """Get the results of a completed enrichment task."""
    redis_data = get_redis_data(task_id)
    
    if redis_data.status != "completed":
        return {
            "task_id": task_id,
            "status": redis_data.status,
            "message": "Task not yet completed",
            "progress": f"{redis_data.numTasksCompleted}/{redis_data.numTasks}",
        }
    
    filtered_results = []
    for result in redis_data.results:
        if result.get("error"):
            continue
        filtered_result = filter_low_confidence_contacts(result)
        filtered_results.append(filtered_result.model_dump())
    
    return {"task_id": task_id, "status": "completed", "results": filtered_results}

