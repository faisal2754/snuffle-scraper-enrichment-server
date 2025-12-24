import os
import json
import time
import logging
import requests
from fastapi import HTTPException
from pydantic import ValidationError
from azure.servicebus import ServiceBusClient, ServiceBusMessage, TransportType

from .models import (
    EnrichmentInput,
    EnrichmentAggregatorInput,
    EnrichmentRedisData,
    Contact,
    CompanyResult,
    ScraperAggregatedOutput,
)
from .redis_client import (
    redis_client,
    update_and_check_task_script,
    TASK_RESULT_TTL,
    MIN_CONFIDENCE_SCORE,
)

logger = logging.getLogger(__name__)


def get_redis_data(task_id: str) -> EnrichmentRedisData:
    """Get data from Redis and parse it into the EnrichmentRedisData model."""
    redis_data = redis_client.get(f"task:{task_id}")
    if not redis_data:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    data = json.loads(redis_data)
    try:
        return EnrichmentRedisData(**data)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Invalid data format for task {task_id}: {str(e)}")


def filter_low_confidence_contacts(company_result: dict) -> CompanyResult:
    """Filter out contacts with confidence score below threshold and flatten to Contact model."""
    try:
        scraper_output = ScraperAggregatedOutput(**company_result)
    except Exception as e:
        logger.warning(f"Failed to parse as ScraperAggregatedOutput: {e}, using raw dict")
        # Fallback to raw dict handling for backwards compatibility
        contacts = company_result.get("contacts", [])
        filtered_contacts = []
        for contact in contacts:
            confidence_score = contact.get("confidenceScore", 0)
            if confidence_score >= MIN_CONFIDENCE_SCORE:
                filtered_contact = Contact(
                    firstName=contact.get("firstName", {}).get("value") if isinstance(contact.get("firstName"), dict) else contact.get("firstName"),
                    lastName=contact.get("lastName", {}).get("value") if isinstance(contact.get("lastName"), dict) else contact.get("lastName"),
                    email=contact.get("email", {}).get("value") if isinstance(contact.get("email"), dict) else contact.get("email"),
                    phone=contact.get("phone", {}).get("value") if isinstance(contact.get("phone"), dict) else contact.get("phone"),
                    linkedinUrl=contact.get("linkedinUrl", {}).get("value") if isinstance(contact.get("linkedinUrl"), dict) else contact.get("linkedinUrl"),
                    role=contact.get("role", {}).get("value") if isinstance(contact.get("role"), dict) else contact.get("role"),
                    confidenceScore=confidence_score,
                )
                filtered_contacts.append(filtered_contact)
        return CompanyResult(
            companyId=company_result.get("companyId"),
            companyName=company_result.get("companyName"),
            contacts=filtered_contacts,
        )
    
    # Use typed models
    filtered_contacts = []
    for contact in scraper_output.contacts:
        if contact.confidenceScore >= MIN_CONFIDENCE_SCORE:
            filtered_contact = Contact(
                firstName=contact.firstName.value if contact.firstName else None,
                lastName=contact.lastName.value if contact.lastName else None,
                email=contact.email.value if contact.email else None,
                phone=contact.phone.value if contact.phone else None,
                linkedinUrl=contact.linkedinUrl.value if contact.linkedinUrl else None,
                role=contact.role.value if contact.role else None,
                confidenceScore=contact.confidenceScore,
            )
            filtered_contacts.append(filtered_contact)
    
    return CompanyResult(
        companyId=scraper_output.companyId,
        companyName=scraper_output.companyName,
        contacts=filtered_contacts,
    )


def process_enqueue_enrichment(input_data: EnrichmentInput, task_id: str):
    """Background task to enqueue company enrichment jobs to Service Bus."""
    queue_name = os.getenv("QUEUE_ENRICHMENT")
    connection_string = os.getenv("SERVICEBUS_CONNECTION_STRING")
    webhook_url = os.getenv("WEBHOOK_URL")
    
    if not queue_name or not connection_string:
        logger.error("Missing QUEUE_ENRICHMENT or SERVICEBUS_CONNECTION_STRING", extra={"task_id": task_id})
        return
    
    companies = input_data.formData
    
    if len(companies) == 0:
        logger.info("No companies to process", extra={"task_id": task_id})
        if webhook_url:
            requests.post(webhook_url, json={"results": []})
        return
    
    data_to_send = [
        {"task_id": task_id, "company_name": company.companyName, "company_id": company.companyId}
        for company in companies
    ]
    
    logger.info(f"Queueing {len(data_to_send)} companies for processing", extra={"task_id": task_id})
    
    max_retries = 3
    batch_size = 10
    
    for attempt in range(max_retries):
        try:
            servicebus_client = ServiceBusClient.from_connection_string(
                connection_string,
                transport_type=TransportType.AmqpOverWebsocket,
                retry_total=3,
                retry_backoff_factor=3,
                retry_backoff_max=30,
            )
            
            with servicebus_client:
                with servicebus_client.get_queue_sender(queue_name) as sender:
                    for i in range(0, len(data_to_send), batch_size):
                        batch_data = data_to_send[i : i + batch_size]
                        batch = sender.create_message_batch()
                        
                        for item in batch_data:
                            message = ServiceBusMessage(json.dumps(item))
                            try:
                                batch.add_message(message)
                            except ValueError:
                                logger.warning(f"Message too large, skipping", extra={"task_id": task_id})
                                continue
                        
                        if len(batch) > 0:
                            sender.send_messages(batch)
                            logger.info(f"Sent batch of {len(batch)} messages", extra={"task_id": task_id})
                        
                        time.sleep(0.5)
            
            logger.info(f"Successfully sent all messages", extra={"task_id": task_id})
            break
            
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to send messages after {max_retries} attempts: {str(e)}", extra={"task_id": task_id})
                raise
            logger.warning(f"Attempt {attempt + 1} failed, retrying...", extra={"task_id": task_id})
            time.sleep(5 + (5 * attempt))


def process_enrichment_aggregation(input_data: EnrichmentAggregatorInput):
    """Background task to aggregate enrichment results."""
    task_id = input_data.task_id
    data = input_data.data
    error = input_data.error
    
    logger.info(f"Processing enrichment aggregation for task:{task_id}", extra={"task_id": task_id})
    
    if error:
        logger.error(f"Error received for task {task_id}: {error}", extra={"task_id": task_id})
        data = data or {"companyId": None, "companyName": None, "contacts": [], "error": error}
    
    key = f"task:{task_id}"
    try:
        script_result = update_and_check_task_script(keys=[key], args=[json.dumps(data), TASK_RESULT_TTL])
    except Exception as e:
        logger.error(f"Lua script update failed: {e}", extra={"task_id": task_id})
        return
    
    if not script_result or not isinstance(script_result, (list, tuple)) or len(script_result) < 3:
        logger.error(f"Unexpected Lua script result: {script_result}", extra={"task_id": task_id})
        return
    
    num_completed, num_tasks, just_completed = script_result[0], script_result[1], script_result[2]
    logger.info(f"Progress: {num_completed}/{num_tasks} companies processed", extra={"task_id": task_id})
    
    if just_completed == 1:
        logger.info(f"All companies processed, preparing final results", extra={"task_id": task_id})
        
        redis_data = get_redis_data(task_id)
        
        filtered_results = []
        for result in redis_data.results:
            if result.get("error"):
                continue
            filtered_result = filter_low_confidence_contacts(result)
            filtered_results.append(filtered_result.model_dump())
        
        json_body = {"taskId": task_id, "results": filtered_results}
        
        webhook_url = redis_data.webhookUrl
        if webhook_url:
            logger.info(f"Sending {len(filtered_results)} company results to webhook", extra={"task_id": task_id})
            try:
                response = requests.post(webhook_url, json=json_body, timeout=30)
                if response.status_code == 200:
                    logger.info(f"Successfully sent results to webhook", extra={"task_id": task_id})
                else:
                    logger.error(f"Failed to send results to webhook. Status: {response.status_code}", extra={"task_id": task_id})
            except Exception as e:
                logger.error(f"Error sending to webhook: {e}", extra={"task_id": task_id})

