"""MongoDB helper utilities for persisting Telegram user information."""

from __future__ import annotations

import os
from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

_MONGO_CLIENT: Optional[AsyncIOMotorClient] = None

# Default connection string provided for deployments where the environment variable is
# not configured. Keeping the value centralised avoids repeating the credential
# throughout the codebase while still allowing overrides via ``MONGODB_URI``.
_DEFAULT_MONGO_URI = (
    "mongodb+srv://nikkivp15174_db_user:qcJuQoBvL8zyMTEb@"
    "cluster0.21r6h5c.mongodb.net/?appName=Cluster0"
)


def _get_client() -> AsyncIOMotorClient:
    """Return a cached Motor client instance using the configured URI."""

    global _MONGO_CLIENT
    if _MONGO_CLIENT is not None:
        return _MONGO_CLIENT

    mongo_uri = os.getenv("MONGODB_URI", _DEFAULT_MONGO_URI)

    _MONGO_CLIENT = AsyncIOMotorClient(mongo_uri)
    return _MONGO_CLIENT


def _get_users_collection() -> AsyncIOMotorCollection:
    """Return the MongoDB collection that stores Telegram users."""

    database_name = os.getenv("MONGODB_DB", "telegram_bot")
    return _get_client()[database_name]["users"]


async def save_user(user_id: int, username: Optional[str], first_name: Optional[str]) -> None:
    """Persist a Telegram user record with basic profile information."""

    collection = _get_users_collection()
    await collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
            }
        },
        upsert=True,
    )


async def get_all_user_ids() -> List[int]:
    """Return all stored Telegram user IDs."""

    collection = _get_users_collection()
    cursor = collection.find({}, {"user_id": 1, "_id": 0})

    user_ids: List[int] = []
    async for document in cursor:
        user_id = document.get("user_id")
        if isinstance(user_id, int):
            user_ids.append(user_id)

    return user_ids
