import asyncio
from typing import List
from uuid import uuid4

import utils
from config import alog
from enums import BOT, ErrorMessage, Message, USER

from fastapi import APIRouter, UploadFile
from langchain import ConversationChain, OpenAI
from langchain.chains.conversational_retrieval.base import (
    BaseConversationalRetrievalChain,
)
from starlette import status
from utils.ai.open_ai import get_text_chunk, insert
from utils.cache import Cache
from utils.chat import get_conversation_v2, resolve_sender
from utils.inputs import pdf
from utils.Time import deltaTime
from utils.uuid import is_valid_uuid

from routers.chat_v2 import create_v2, upload_v2

router = APIRouter(tags=['chat', 'v3'])
cache = Cache(
    maxsize=10000, )  # ttl=deltaTime(hour=10).total_seconds(),


def get_conversation_v3(chat_id: str) -> ConversationChain | BaseConversationalRetrievalChain:
    conversation: ConversationChain | BaseConversationalRetrievalChain = cache.get(
        chat_id,
    )

    if conversation is not None:
        return conversation

    llm = OpenAI(temperature=0)
    conversation: ConversationChain = ConversationChain(llm=llm, verbose=True)

    cache.set(chat_id, conversation)

    return conversation


@router.get('/v3/{chat_id}')
async def get_chat(chat_id: str) -> dict[str, list[Message] | int]:
    conversation: ConversationChain | BaseConversationalRetrievalChain = get_conversation_v3(
        chat_id,
    )
    msgs: List[Message] = []

    for i, msg in enumerate(conversation.memory.chat_memory.messages):
        _msg = Message(resolve_sender(msg), msg.content, chat_id)
        msgs.append(_msg)

    return {'total': len(msgs), 'msgs': msgs}


@router.post('/v3')  # release: using conversation chain
async def create_v3(msg: Message):
    answer = Message(BOT, None, msg.chat_id)
    task = asyncio.create_task(create_v2(msg))

    conversation: ConversationChain = get_conversation_v3(answer.chat_id)

    if isinstance(conversation, ConversationChain):  # FIXME remove
        task.cancel('invalid task')
        answer.message = conversation.predict(input=msg.message)
        return answer
    elif isinstance(conversation, BaseConversationalRetrievalChain):
        try:
            done = await asyncio.wait_for(task, deltaTime(min=.5).total_seconds())
        except asyncio.TimeoutError:
            return ErrorMessage(
                'Gave up waiting, task canceled', msg.chat_id, status.HTTP_408_REQUEST_TIMEOUT,
            )
        except Exception as e:
            return ErrorMessage(
                e, msg.chat_id, status.HTTP_422_UNPROCESSABLE_ENTITY,
            )()
        return done
    else:
        task.cancel('invalid task')
        raise ValueError(
            f'Invalid conversation chain {conversation.__class__}',
        )


@router.put('/{chat_id}/upload/v3')
async def upload(chat_id: str, file: UploadFile):
    if not is_valid_uuid(chat_id):  # For beginning of new conversation
        alog.error(__name__, 'invalid chat_id', chat_id)
        chat_id = uuid4().hex

    task = asyncio.create_task(upload_v2(chat_id, file))

    if file.content_type != 'application/pdf':
        task.cancel('invalid task')
        return ErrorMessage(
            'Only pdf files are supported currently', chat_id, status.HTTP_400_BAD_REQUEST,
        )()

    try:
        # data = pdf.extract(file.file)
        # # Use loader and data splitter to make a document list
        # doc = get_text_chunk(data)
        # # Upsert data to the VectorStore
        # insert(doc, namespace=chat_id)
        #
        # prompt_tmpl = Message(
        #     USER,
        #     f"""uploaded a pdf file-{file.filename} which will serve as context for our conversation""",
        #     chat_id,
        # )

        # conversation = get_conversation_v2(chat_id)
        #
        # c = get_conversation_v3(chat_id)
        #
        # if isinstance(c, ConversationChain):
        #     # conversation.memory = c.memory #FIXME: trouble code
        #     cache.set(chat_id, conversation)
        #
        # task = asyncio.create_task(create_v3(prompt_tmpl))
        # await asyncio.wait([task], timeout=pow(10, -7))

        try:
            done = await asyncio.wait_for(task, deltaTime(min=.5).total_seconds())
        except asyncio.TimeoutError:
            return ErrorMessage(
                'Gave up waiting, task canceled', chat_id, status.HTTP_408_REQUEST_TIMEOUT,
            )
        except Exception as e:
            return ErrorMessage(
                e, chat_id, status.HTTP_422_UNPROCESSABLE_ENTITY,
            )()

        cache.set(done.chat_id, get_conversation_v2(done.chat_id))
        return done

    except Exception as e:
        return ErrorMessage(
            e, chat_id, status.HTTP_422_UNPROCESSABLE_ENTITY,
        )()
