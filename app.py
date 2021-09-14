# A Bare Bones Slack API
# Illustrates basic usage of FastAPI w/ MongoDB
import os

from pymongo import MongoClient
from fastapi import FastAPI, status, Depends, Header, HTTPException
from pydantic import BaseModel
from typing import List, Any

DB = "slack"
MSG_COLLECTION = "messages"


# Message class defined in Pydantic
class Message(BaseModel):
    channel: str
    author: str
    text: str


# Instantiate the FastAPI
app = FastAPI()


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class Database(metaclass=SingletonMeta):
    client: MongoClient
    connection: Any

    def get_connection(self) -> MongoClient:
        return self.client

    def set_connection(self, client: MongoClient):
        self.client = client

    def close(self):
        self.client.close()


@app.on_event("startup")
async def startup_event():
    db = Database()
    db.set_connection(MongoClient(host="localhost", port=9999))


@app.on_event("shutdown")
async def startup_event():
    db = Database()
    db.close()


def get_db() -> MongoClient:
    db = Database()
    return db.get_connection()


def verify_token(x_token: str = Header(...)):
    if x_token == os.getenv("secret"):
        return
    raise HTTPException(status_code=401, detail="X-Token header invalid")


@app.get("/status", dependencies=[Depends(verify_token)])
def get_status():
    """Get status of messaging server."""
    return {"status": "running"}


@app.get("/channels", response_model=List[str], dependencies=[Depends(verify_token)])
def get_channels(client: MongoClient = Depends(get_db)):
    """Get all channels in list form."""
    msg_collection = client[DB][MSG_COLLECTION]
    distinct_channel_list = msg_collection.distinct("channel")
    return distinct_channel_list


@app.get("/messages/{channel}", response_model=List[Message], dependencies=[Depends(verify_token)])
def get_messages(channel: str, client: MongoClient = Depends(get_db)):
    """Get all messages for the specified channel."""
    msg_collection = client[DB][MSG_COLLECTION]
    msg_list = msg_collection.find({"channel": channel})
    response_msg_list = []
    for msg in msg_list:
        response_msg_list.append(Message(**msg))
    return response_msg_list


@app.post("/post_message", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_token)])
def post_message(message: Message, client: MongoClient = Depends(get_db)):
    """Post a new message to the specified channel."""
    msg_collection = client[DB][MSG_COLLECTION]
    result = msg_collection.insert_one(message.dict())
    ack = result.acknowledged
    return {"insertion": ack}
