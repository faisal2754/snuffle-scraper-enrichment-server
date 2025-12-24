from pydantic import BaseModel, Field
from typing import List, Optional, Any


class CompanyInput(BaseModel):
    """Single company input for scraper."""
    companyName: str = Field(..., description="Name of the company to research")
    companyId: int = Field(..., description="Unique identifier for this company")


class ScraperInput(BaseModel):
    """Input parameters for the scraper run."""
    formData: List[CompanyInput] = Field(..., description="List of companies to research")


class Contact(BaseModel):
    """Contact information for an HR/executive person."""
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedinUrl: Optional[str] = None
    role: Optional[str] = None
    confidenceScore: int = Field(..., ge=0, le=100, description="Confidence score 0-100")


class CompanyResult(BaseModel):
    """Result for a single company with all found contacts."""
    companyId: int
    companyName: str
    contacts: List[Contact] = Field(default_factory=list)


class ScraperRedisData(BaseModel):
    """Redis data model for scraper tasks."""
    task_id: str
    status: str
    create_time: float
    numTasks: int
    numTasksCompleted: int
    results: List[Any] = Field(default_factory=list)
    errors: List[Any] = Field(default_factory=list)
    webhookUrl: str


class ScraperAggregatorInput(BaseModel):
    """Input for the scraper aggregator endpoint."""
    task_id: str
    data: Optional[dict] = None
    error: Optional[dict] = None

