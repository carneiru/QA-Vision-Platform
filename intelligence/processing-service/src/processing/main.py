from src.processing-service.api.main import app

if __name__ == "__main__":
    import uvicorn
    from src.processing-service.core.config import settings
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )
