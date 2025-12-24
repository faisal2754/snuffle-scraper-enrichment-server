from pydantic import BaseModel, Field
from typing import List, Optional, Any


class CompanyInput(BaseModel):
    """Single company input for enrichment."""
    companyName: str = Field(..., description="Name of the company to research")
    companyId: int = Field(..., description="Unique identifier for this company")


class EnrichmentInput(BaseModel):
    """Input parameters for the enrichment run."""
    formData: List[CompanyInput] = Field(..., description="List of companies to research")


# --- CrewAI Service Output Models (input to aggregator) ---

class Source(BaseModel):
    """Source information for a data point."""
    description: Optional[str] = None
    url: Optional[str] = None


class ValueWithConfidence(BaseModel):
    """A value with its sources and confidence score."""
    value: Optional[str] = None
    sources: List[Source] = Field(default_factory=list)
    confidence: Optional[float] = None


class ContactWithSources(BaseModel):
    """Contact information with sources and confidence per field."""
    firstName: Optional[ValueWithConfidence] = None
    lastName: Optional[ValueWithConfidence] = None
    email: Optional[ValueWithConfidence] = None
    phone: Optional[ValueWithConfidence] = None
    linkedinUrl: Optional[ValueWithConfidence] = None
    role: Optional[ValueWithConfidence] = None
    confidenceScore: float = Field(..., ge=0.0, le=1.0)


class ScraperAggregatedOutput(BaseModel):
    """Output from CrewAI scraper service."""
    companyId: int
    companyName: str
    contacts: List[ContactWithSources] = Field(default_factory=list)

    class Config:
        extra = "ignore"


# --- Flattened Output Models (sent to webhook) ---

class Contact(BaseModel):
    """Flattened contact information for webhook output."""
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedinUrl: Optional[str] = None
    role: Optional[str] = None
    confidenceScore: float = Field(..., ge=0, le=1, description="Confidence score 0-1")


class CompanyResult(BaseModel):
    """Flattened result for webhook output."""
    companyId: int
    companyName: str
    contacts: List[Contact] = Field(default_factory=list)


class EnrichmentRedisData(BaseModel):
    """Redis data model for enrichment tasks."""
    task_id: str
    status: str
    create_time: float
    numTasks: int
    numTasksCompleted: int
    results: List[Any] = Field(default_factory=list)
    errors: List[Any] = Field(default_factory=list)
    webhookUrl: str


class EnrichmentAggregatorInput(BaseModel):
    """Input for the enrichment aggregator endpoint."""
    task_id: str
    data: Optional[dict] = None
    error: Optional[dict] = None

