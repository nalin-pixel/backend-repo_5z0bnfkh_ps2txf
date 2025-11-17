import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Item, Warehouse, Supplier, InventoryMovement, ShipmentCreate, ShipmentUpdateStatus, Shipment

app = FastAPI(title="Shipping & Logistics Inventory API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Utilities
class IdModel(BaseModel):
    id: str


def to_obj_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


@app.get("/")
def root():
    return {"message": "Shipping & Logistics Inventory API"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "❌ Not Set"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response


# Basic CRUD endpoints for core entities
@app.post("/items", response_model=dict)
def create_item(item: Item):
    inserted_id = create_document("item", item)
    return {"id": inserted_id}


@app.get("/items", response_model=list)
def list_items(q: Optional[str] = None, limit: int = 50):
    filter_dict = {}
    if q:
        filter_dict = {"$or": [{"sku": {"$regex": q, "$options": "i"}}, {"name": {"$regex": q, "$options": "i"}}]}
    docs = get_documents("item", filter_dict, limit)
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


@app.post("/warehouses", response_model=dict)
def create_warehouse(warehouse: Warehouse):
    inserted_id = create_document("warehouse", warehouse)
    return {"id": inserted_id}


@app.get("/warehouses", response_model=list)
def list_warehouses(limit: int = 50):
    docs = get_documents("warehouse", {}, limit)
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


@app.post("/suppliers", response_model=dict)
def create_supplier(supplier: Supplier):
    inserted_id = create_document("supplier", supplier)
    return {"id": inserted_id}


@app.get("/suppliers", response_model=list)
def list_suppliers(limit: int = 50):
    docs = get_documents("supplier", {}, limit)
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


# Inventory and shipments
@app.post("/inventory/move", response_model=dict)
def inventory_move(mv: InventoryMovement):
    # record movement
    movement_id = create_document("inventorymovement", mv)
    # adjust stock per warehouse+item snapshot document
    # We keep a simple snapshot collection: stock_{warehouse}_{item}
    key = {"warehouse_id": mv.warehouse_id, "item_id": mv.item_id}
    doc = db["stock"].find_one(key)
    qty = doc.get("quantity", 0) if doc else 0
    qty = qty + mv.quantity if mv.type == "in" else qty - mv.quantity
    if doc:
        db["stock"].update_one(key, {"$set": {"quantity": qty}})
    else:
        db["stock"].insert_one({**key, "quantity": qty})
    return {"movement_id": movement_id, "quantity": qty}


@app.get("/inventory/stock", response_model=list)
def get_stock(warehouse_id: Optional[str] = None, item_id: Optional[str] = None, limit: int = 200):
    filt = {}
    if warehouse_id:
        filt["warehouse_id"] = warehouse_id
    if item_id:
        filt["item_id"] = item_id
    docs = list(db["stock"].find(filt).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


@app.post("/shipments", response_model=dict)
def create_shipment(payload: ShipmentCreate):
    # create shipment doc
    ship = {
        "shipment_no": payload.shipment_no,
        "origin_warehouse_id": payload.origin_warehouse_id,
        "destination_warehouse_id": payload.destination_warehouse_id,
        "destination_name": payload.destination_name,
        "status": "created",
        "items": [i.model_dump() for i in payload.items],
    }
    inserted = db["shipment"].insert_one(ship)

    # reserve inventory (move out as reserved/picked when status changes)
    return {"id": str(inserted.inserted_id)}


@app.patch("/shipments/{shipment_id}/status", response_model=dict)
def update_shipment_status(shipment_id: str, body: ShipmentUpdateStatus):
    ship = db["shipment"].find_one({"_id": to_obj_id(shipment_id)})
    if not ship:
        raise HTTPException(status_code=404, detail="Shipment not found")

    status = body.status
    db["shipment"].update_one({"_id": ship["_id"]}, {"$set": {"status": status}})

    # perform inventory movements at key transitions
    if status == "picked":
        # reserve stock (out) from origin
        for it in ship.get("items", []):
            mv = InventoryMovement(type="out", warehouse_id=ship["origin_warehouse_id"], item_id=it["item_id"], quantity=it["quantity"], reference=ship.get("shipment_no"))
            inventory_move(mv)
    if status == "delivered":
        # add stock (in) to destination if internal transfer
        if ship.get("destination_warehouse_id"):
            for it in ship.get("items", []):
                mv = InventoryMovement(type="in", warehouse_id=ship["destination_warehouse_id"], item_id=it["item_id"], quantity=it["quantity"], reference=ship.get("shipment_no"))
                inventory_move(mv)

    return {"status": status}


@app.get("/shipments", response_model=list)
def list_shipments(limit: int = 50):
    docs = list(db["shipment"].find({}).sort("_id", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
