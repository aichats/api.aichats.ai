import dataclasses
from functools import cache
from typing import Dict, List, TypeVar
from uuid import uuid4

import langchain
from fastapi import APIRouter, status, UploadFile
from fastapi.responses import JSONResponse
from icecream import ic
from langchain import ConversationChain, OpenAI

from utils.ai.open_ai import get_text_chunk, insert
from utils.inputs import pdf

router = APIRouter(tags=['chat'])

SENDER = TypeVar('SENDER', str, str)
BOT: SENDER = 'bot'
USER: SENDER = 'user'


# cache = Cache(
#     maxsize=10000, ttl=deltaTime(min=20).total_seconds(),
# )


@dataclasses.dataclass
class Message:
    sender: SENDER
    message: str
    chat_id: str = None


@dataclasses.dataclass
class ErrorMessage:
    error: str | Exception
    chat_id: str


# @router.get('/') #Need DB
# async def get_list():  # TODO:
#     return {'chats': []}
@cache
def get_conversation(chat_id: str) -> ConversationChain:
    # conversation = cache.get(chat_id)
    # if conversation is not None: return conversation

    llm = OpenAI(temperature=0)
    conversation = ConversationChain(llm=llm, verbose=True)
    return conversation


@router.get('/{chat_id}')  # TODO:
async def get(chat_id: str) -> dict[str, list[Message] | int]:
    conversation = get_conversation(chat_id)
    msgs: List[Message] = []
    for i, msg in enumerate(conversation.memory.chat_memory.messages):
        if isinstance(msg, langchain.schema.AIMessage):
            sender = BOT
        else:
            sender = USER

        _class = msg.__class__
        ic(i, msg.content, _class)
        msgs.append(Message(sender, msg.content, chat_id))

    return {'total': len(msgs), 'msgs': msgs}


@router.post('/')
async def create(msg: Message):
    answer = Message(BOT, None, msg.chat_id or uuid4())

    conversation = get_conversation(answer.chat_id)
    answer.message = conversation.predict(input=msg.message)

    return answer


@router.post('/{chat_id}/upload')
async def upload(chat_id: str, file: UploadFile):  # TODO: support multiple

    if file is None or file.content_type != 'application/pdf':
        res = JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorMessage(
                'No file attached',
            ),
        )
        if file.content_type != 'application/pdf':
            res.content = ErrorMessage('Only pdf files are supported', chat_id)

        return res

    # conversation = get_conversation(chat_id)
    chat_id = chat_id or uuid4()

    try:
        data = pdf.extract(file.file)
        # Use loader and data splitter to make a document list
        doc = get_text_chunk(data)
        ic(f'text_chunks are generated and the total chucks are {len(doc)}')

        # Upsert data to the VectorStore
        insert(doc)

        return Message(BOT, 'uploaded successfully', chat_id)
    except Exception as e:
        return ErrorMessage(e, chat_id)
