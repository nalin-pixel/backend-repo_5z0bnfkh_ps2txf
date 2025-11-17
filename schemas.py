"""
Database Schemas for Shipping & Logistics Inventory

Each Pydantic model represents a MongoDB collection. The collection name is the
lowercase class name (e.g., Item -> "item").
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class Item(BaseModel):
    sku: str = Field(..., description="Stock keeping unit (unique code)")
    name: str = Field(..., description="Item name")
    description: Optional[str] = Field(None, description="Item description")
    unit: str = Field("pcs", description="Unit of measure, e.g., pcs, box, kg")
    barcode: Optional[str] = Field(None, description="Barcode/QR code")
    weight_kg: Optional[float] = Field(None, ge=0, description="Weight in kg")
    dimensions_cm: Optional[str] = Field(None, description="LxWxH in cm (string)")
    is_active: bool = Field(True, description="Whether the item is active")


class Warehouse(BaseModel):
    code: str = Field(..., description="Warehouse short code")
    name: str = Field(..., description="Warehouse name")
    address: Optional[str] = Field(None, description="Address")
    city: Optional[str] = Field(None, description="City")
    country: Optional[str] = Field(None, description="Country")
    is_active: bool = Field(True, description="Whether the warehouse is active")


class Supplier(BaseModel):
    name: str = Field(..., description="Supplier name")
    contact: Optional[str] = Field(None, description="Contact person")
    email: Optional[str] = Field(None, description="Email")
    phone: Optional[str] = Field(None, description="Phone")
    address: Optional[str] = Field(None, description="Address")


class MovementItem(BaseModel):
    item_id: str = Field(..., description="Item document id (string)")
    quantity: float = Field(..., gt=0, description="Quantity moved")


class InventoryMovement(BaseModel):
    type: str = Field(..., description="in | out")
    warehouse_id: str = Field(..., description="Warehouse document id (string)")
    item_id: str = Field(..., description="Item document id (string)")
    quantity: float = Field(..., gt=0, description="Quantity moved")
    reference: Optional[str] = Field(None, description="PO/SO/Reference number")
    notes: Optional[str] = Field(None, description="Notes")
    related_id: Optional[str] = Field(None, description="Related doc (e.g., shipment id)")


class ShipmentCreate(BaseModel):
    shipment_no: str = Field(..., description="Shipment number")
    origin_warehouse_id: str = Field(..., description="Origin warehouse id")
    destination_warehouse_id: Optional[str] = Field(None, description="Destination warehouse id if internal")
    destination_name: Optional[str] = Field(None, description="External destination name if not internal")
    items: List[MovementItem] = Field(..., description="Items and quantities")


class ShipmentUpdateStatus(BaseModel):
    status: str = Field(..., description="created | picked | in_transit | delivered | cancelled")


class Shipment(BaseModel):
    shipment_no: str
    origin_warehouse_id: str
    destination_warehouse_id: Optional[str] = None
    destination_name: Optional[str] = None
    status: str = Field("created")
    items: List[MovementItem]
    carrier: Optional[str] = None
    tracking_number: Optional[str] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
