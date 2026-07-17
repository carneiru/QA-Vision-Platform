from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def root():
    return {"message": "Plugin Catalog API v1"}

@router.get("/plugins")
async def get_plugins():
    return {"plugins": []}

@router.post("/plugins")
async def create_plugin(plugin: dict):
    return {"message": "Plugin created", "plugin": plugin}

@router.get("/plugins/{plugin_id}")
async def get_plugin(plugin_id: str):
    return {"plugin_id": plugin_id, "details": {}}

@router.put("/plugins/{plugin_id}")
async def update_plugin(plugin_id: str, plugin: dict):
    return {"message": f"Plugin {plugin_id} updated", "plugin": plugin}

@router.delete("/plugins/{plugin_id}")
async def delete_plugin(plugin_id: str):
    return {"message": f"Plugin {plugin_id} deleted"}
