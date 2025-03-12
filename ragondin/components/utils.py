from abc import ABCMeta
import asyncio
from pathlib import Path
from langchain_core.documents.base import Document

import asyncio
from collections import deque
from typing import Optional
from config.config import load_config
import atexit


config = load_config()

class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]

class SingletonABCMeta(ABCMeta, SingletonMeta):
    pass


class LLMSemaphore(metaclass=SingletonMeta):
    def __init__(self, max_concurrent_ops: int):
        if max_concurrent_ops <= 0:
            raise ValueError("max_concurrent_ops must be a positive integer")
        self.max_concurrent_ops = max_concurrent_ops
        self._semaphore = asyncio.Semaphore(max_concurrent_ops)
        atexit.register(self.cleanup)

    async def __aenter__(self):
        await self._semaphore.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._semaphore.release()

    async def acquire(self):
        await self._semaphore.acquire()

    def release(self):
        self._semaphore.release()
    
    def cleanup(self):
        """ Ensure semaphore is released at shutdown """
        while self._semaphore.locked():
            self._semaphore.release()
    

def load_sys_template(file_path: Path) -> tuple[str, str]:
    with open(file_path, mode="r") as f:
        sys_msg = f.read()
        return sys_msg
    

def format_context(docs: list[Document]) -> str:
    """Build context string from list of documents."""
    if not docs:
        return 'No document found from the database', []
    
    sources = []
    context = "Extracted documents:\n"

    for i, doc in enumerate(docs, start=1):
        doc_id = f"[doc_{i}]"
        document = f"""
        *source*: {doc_id}
        content: \n{doc.page_content.strip()}\n
        """

        # document = (f"""<chunk document_id={doc_id}>\n{doc.page_content.strip()}\n</chunk>\n""")
        # Source: {source} (Page: {page})
    
        context += document
        context += "-" * 40 + "\n\n"

        sources.append(
            {
                "doc_id": doc_id,
                'source': doc.metadata["source"],
                'sub_url_path': doc.metadata["sub_url_path"],
                'page': doc.metadata["page"],
                'content': doc.page_content
            }
        )
    return context, sources

# Global variables
llmSemaphore = LLMSemaphore(max_concurrent_ops=config.semaphore.llm_semaphore)