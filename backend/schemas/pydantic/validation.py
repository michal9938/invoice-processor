"""
Pydantic schemas for validation-related requests and responses
Handles validation status, errors, and mismatch reporting
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum


class ValidationStatus(str, Enum):
    """Invoice line validation statuses"""
    PENDING = "pending"
    VALIDATED = "validated"
    NEEDS_REVIEW = "needs_review"
    DISPUTED = "disputed"
    ERROR = "error"


class ErrorType(str, Enum):
    """Types of validation errors"""
    UNIT_PRICE_MISMATCH = "unit_price_mismatch"
    QUANTITY_MISMATCH = "quantity_mismatch"
    LINE_TOTAL_MISMATCH = "line_total_mismatch"
    SKU_NOT_FOUND = "sku_not_found"
    PRICE_NOT_FOUND = "price_not_found"
    PRICE_EXPIRED = "price_expired"


class ValidationError(BaseModel):
    """Schema for validation error details"""
    line_id: UUID = Field(..., description="Invoice line ID")
    error_type: ErrorType = Field(..., description="Type of validation error")
    message: str = Field(..., description="Error message")
    expected_value: Optional[float] = Field(None, description="Expected value")
    actual_value: Optional[float] = Field(None, description="Actual value from invoice")
    tolerance_percent: Optional[float] = Field(None, description="Applied tolerance percentage")


class ValidationResult(BaseModel):
    """Schema for validation result response"""
    invoice_id: UUID = Field(..., description="Invoice ID")
    status: str = Field(..., description="Overall invoice status")
    total_lines: int = Field(..., description="Total number of invoice lines")
    validated_lines: int = Field(..., description="Number of validated lines")
    error_lines: int = Field(..., description="Number of lines with errors")
    errors: List[ValidationError] = Field(default_factory=list, description="List of validation errors")
    validated_at: Optional[datetime] = Field(None, description="Validation timestamp")


class PriceAcceptanceRequest(BaseModel):
    """Schema for accepting a new price"""
    invoice_line_id: UUID = Field(..., description="Invoice line ID")
    new_price: float = Field(..., gt=0, description="New price to accept")
    reason: str = Field(..., description="Reason for price acceptance")
    valid_from: datetime = Field(..., description="Valid from date for the new price")


class DisputeRequest(BaseModel):
    """Schema for disputing an invoice"""
    invoice_id: UUID = Field(..., description="Invoice ID")
    reason: str = Field(..., description="Reason for dispute")
    line_ids: Optional[List[UUID]] = Field(None, description="Specific line IDs to dispute")


class DisputeResponse(BaseModel):
    """Schema for dispute response"""
    invoice_id: UUID
    status: str
    dispute_summary: str
    disputed_at: datetime

