from components.indexer.indexer import Indexer
from crud.qdrant import QdrantCRUD
from crud.milvus import MilvusCRUD
from config import load_config
from loguru import logger

# load config
config = load_config()
# Initialize components once
indexer = Indexer(config, logger)
qdrant_crud = QdrantCRUD(indexer)

def get_qdrant_crud():
    return qdrant_crud

# Instead of initializing QdrantCRUD, we initialize MilvusCRUD
milvus_crud = MilvusCRUD(indexer)

def get_milvus_crud():
    return milvus_crud