"""
Database Initialization
"""
from .mongodb import db

async def connect_to_mongo():
    await db.connect()

async def close_mongo_connection():
    await db.close()