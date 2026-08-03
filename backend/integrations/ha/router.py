from fastapi import APIRouter, Depends
from auth import verify_api_key
from integrations.ha.client import ha_status, ha_lock, ha_garage, ha_restart
from pydantic import BaseModel

router = APIRouter(prefix="/integrations/ha", tags=["home-assistant"],
                   dependencies=[Depends(verify_api_key)])


@router.get("/status")
def status():
    return {"result": ha_status()}


@router.post("/lock")
def lock():
    return {"result": ha_lock()}


class GarageCmd(BaseModel):
    door: str = "double"
    action: str = "open"


@router.post("/garage")
def garage(body: GarageCmd):
    return {"result": ha_garage(body.door, body.action)}


@router.post("/restart")
def restart():
    return {"result": ha_restart()}
