from pydantic import BaseModel, Field
from typing import List, Optional, Any


class CompanyInput(BaseModel):
    """Single company input for enrichment."""
    companyName: str = Field(..., description="Name of the company to research")
    companyId: int = Field(..., description="Unique identifier for this company")


class EnrichmentInput(BaseModel):
    """Input parameters for the enrichment run."""
    formData: List[CompanyInput] = Field(..., description="List of companies to research")


class Contact(BaseModel):
    """Contact information for an HR/executive person."""
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedinUrl: Optional[str] = None
    role: Optional[str] = None
    confidenceScore: float = Field(..., ge=0, le=1, description="Confidence score 0-1")


class CompanyResult(BaseModel):
    """Result for a single company with all found contacts."""
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

