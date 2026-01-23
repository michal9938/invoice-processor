"""
Pydantic schemas for invoice-related requests and responses
Validates invoice data structures for API endpoints
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class InvoiceBase(BaseModel):
    """Base schema for invoice data"""
    supplier: str = Field(..., description="Supplier name")
    invoice_number: str = Field(..., description="Invoice number")
    invoice_date: datetime = Field(..., description="Invoice date")
    status: Optional[str] = Field(default="pending", description="Invoice status")


class InvoiceCreate(InvoiceBase):
    """Schema for creating a new invoice"""
    currency: Optional[str] = Field(default="USD", description="Invoice currency")
    email_reference: Optional[str] = Field(None, description="Email message ID reference")


class InvoiceResponse(InvoiceBase):
    """Schema for invoice response"""
    id: UUID
    currency: Optional[str] = None
    email_reference: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InvoiceLineBase(BaseModel):
    """Base schema for invoice line data"""
    sku: str = Field(..., description="Product SKU")
    product_name: str = Field(..., description="Product name")
    quantity: float = Field(..., gt=0, description="Quantity")
    unit_price: float = Field(..., gt=0, description="Unit price")
    line_total: float = Field(..., gt=0, description="Line total")


class InvoiceLineCreate(InvoiceLineBase):
    """Schema for creating a new invoice line"""
    invoice_id: UUID = Field(..., description="Parent invoice ID")
    status: Optional[str] = Field(default=None, description="Validation status")


class InvoiceLineResponse(InvoiceLineBase):
    """Schema for invoice line response"""
    id: UUID
    invoice_id: UUID
    status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InvoiceWithLines(InvoiceResponse):
    """Schema for invoice with its lines"""
    lines: List[InvoiceLineResponse] = Field(default_factory=list)


class ManualUploadRequest(BaseModel):
    """Schema for manual invoice upload"""
    supplier: str = Field(..., description="Supplier name")
    invoice_number: str = Field(..., description="Invoice number")
    invoice_date: datetime = Field(..., description="Invoice date")
    currency: Optional[str] = Field(default="USD", description="Invoice currency")

