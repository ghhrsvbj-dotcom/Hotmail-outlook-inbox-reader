"""MongoDB helper utilities for persisting Telegram user information."""

from __future__ import annotations

import os
from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

_MONGO_CLIENT: Optional[AsyncIOMotorClient] = None


def _get_client() -> AsyncIOMotorClient:
    """Return a cached Motor client instance using the configured URI."""

    global _MONGO_CLIENT
    if _MONGO_CLIENT is not None:
        return _MONGO_CLIENT

    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError("MONGODB_URI environment variable must be set to use MongoDB features.")

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
