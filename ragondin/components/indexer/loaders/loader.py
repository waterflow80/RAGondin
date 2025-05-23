import asyncio
import gc
import importlib
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional

import torch
from aiopath import AsyncPath
from langchain_core.documents.base import Document
from loguru import logger

from .base import BaseLoader
from .DoclingLoader import DoclingLoader
from .MarkerLoader import MarkerLoader
from .VideoAudioLoader import VideoAudioLoader


class DocSerializer:
    """
    A class used to serialize documents asynchronously.
    Attributes:
        data_dir (str, optional): The directory where the data is stored.
        kwargs (dict): Additional keyword arguments to pass to the loader.
    Methods:
        serialize_document(path: str, semaphore: asyncio.Semaphore, metadata: Optional[Dict] = {}) -> Document:
            Asynchronously serializes a single document from the given path.
        serialize_documents(path: str | Path | list[str], metadata: Optional[Dict] = {}, recursive=True, n_concurrent_ops=3) -> AsyncGenerator[Document, None]:
    """

    def __init__(self, data_dir=None, **kwargs) -> None:
        self.data_dir = data_dir
        self.kwargs = kwargs
        self.config = kwargs.get("config")
        self.loader_classes = get_loaders(
            file_loaders=self.config.loader["file_loaders"]
        )

    async def serialize_document(self, path: str, metadata: Optional[Dict] = {}):
        p = AsyncPath(path)
        type_ = p.suffix

        loader_cls: BaseLoader = self.loader_classes.get(type_, None)
        if loader_cls is None:
            logger.info(f"No loader for this file {p.name}")
            return None

        logger.debug(f"LOADING: {p.name}")
        loader = loader_cls(**self.kwargs)  # Propagate kwargs here!
        metadata = {"page_sep": loader.page_sep, **metadata}
        doc: Document = await loader.aload_document(
            file_path=path, metadata=metadata, save_md=False
        )

        if isinstance(loader, (DoclingLoader, MarkerLoader, VideoAudioLoader)):
            loader_cls.destroy()

        del loader

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()

        return doc

    async def serialize_documents(
        self,
        path: str | Path | list[str],
        metadata: Optional[Dict] = {},
        recursive=True,
    ) -> AsyncGenerator[Document, None]:
        tasks = []
        async for file in get_files(self.loader_classes, path, recursive):
            tasks.append(self.serialize_document(file, metadata=metadata))

        for task in asyncio.as_completed(tasks):
            doc = await task
            yield doc  # yield doc as soon as it is ready


async def get_files(
    loaders: Dict[str, BaseLoader], path: str | list = True, recursive=True
) -> AsyncGenerator:
    """Get files from a directory or a list of files"""

    supported_types = loaders.keys()
    patterns = [f"**/*{type_}" for type_ in supported_types]

    if isinstance(path, list):
        for file_path in path:
            p = AsyncPath(file_path)
            if await p.is_file():
                type_ = p.suffix
                if type_ in supported_types:  # check the file type
                    yield p
                else:
                    logger.warning(
                        f"Unsupported file type: {type_}: {p.name} will not be indexed."
                    )

    else:
        p = AsyncPath(path)
        if await p.is_dir():
            for pat in patterns:
                async for file in p.rglob(pat) if recursive else p.glob(pat):
                    yield file
        elif await p.is_file():
            type_ = p.suffix
            if type_ in supported_types:  # check the file type
                yield p
            else:
                logger.warning(
                    f"Unsupported file type: {type_}: {p.name} will not be indexed."
                )
        else:
            raise ValueError(f"Path {path} is neither a file nor a directory")


def get_loaders(file_loaders: dict):
    loader_classes = {}

    for type_, class_name in file_loaders.items():
        try:
            module = importlib.import_module(f"components.indexer.loaders.{class_name}")
            cls = getattr(module, class_name)
            loader_classes[f".{type_}"] = cls
            logger.debug(f"Loaded {class_name} for {type_}")
        except (ModuleNotFoundError, AttributeError) as e:
            logger.error(f"Error loading {class_name}: {e}")

    logger.debug(f"Loaders loaded: {loader_classes.keys()}")
    return loader_classes
