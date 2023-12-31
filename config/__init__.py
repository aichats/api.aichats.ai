import logging

from icecream import ic
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Pinecone

from config import log, open_ai, pinecone
from config.constants import INDEX_NAME

alog: logging.Logger = logging.getLogger('app')


def setup():
    log.setup()
    pinecone.setup()
    open_ai.setup()
    ic('setup of log, openai, pinecone complete')
