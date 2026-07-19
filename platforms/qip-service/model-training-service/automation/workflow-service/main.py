#!/usr/bin/env python3
"""
Workflow Designer Service Main Entry Point
"""
import uvicorn
from src.workflow.api.main import app

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)