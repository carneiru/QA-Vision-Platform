from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def root():
    return {"message": "Compatibility API v1"}

@router.get("/checks")
async def get_compatibility_checks():
    return {"checks": []}

@router.post("/checks")
async def create_compatibility_check(check: dict):
    return {"message": "Compatibility check created", "check": check}

@router.get("/checks/{check_id}")
async def get_compatibility_check(check_id: str):
    return {"check_id": check_id, "details": {}}

@router.put("/checks/{check_id}")
async def update_compatibility_check(check_id: str, check: dict):
    return {"message": f"Compatibility check {check_id} updated", "check": check}

@router.delete("/checks/{check_id}")
async def delete_compatibility_check(check_id: str):
    return {"message": f"Compatibility check {check_id} deleted"}
