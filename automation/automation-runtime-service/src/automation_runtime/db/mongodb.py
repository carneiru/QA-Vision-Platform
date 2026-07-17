"""
MongoDB Database Connection
"""
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import os
from dotenv import load_dotenv

load_dotenv()

class MongoDB:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None

    async def connect(self):
        """Connect to MongoDB"""
        mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        database_name = os.getenv("MONGODB_DATABASE", "automation_runtime_db")

        self.client = AsyncIOMotorClient(mongo_url)
        self.database = self.client[database_name]

    async def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()

    def get_collection(self, collection_name: str):
        """Get a collection from the database"""
        if self.database is None:
            raise RuntimeError("Database not initialized. Call connect() first.")
        return self.database[collection_name]

# Global database instance
db = MongoDB()
