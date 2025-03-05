from loguru import logger
from typing import Optional, Any, List
from fastapi import APIRouter, HTTPException, status, File, UploadFile, Depends, Form
from fastapi.responses import JSONResponse
from pathlib import Path
from crud.qdrant import QdrantCRUD
from models.indexer import SearchRequest, DeleteFilesRequest
from utils.dependencies import get_qdrant_crud
from config.config import load_config
import json

#load config
config = load_config()
DATA_DIR = config.paths.data_dir
# Create an APIRouter instance
router = APIRouter()


@router.post("/add-files/", response_model=None)
async def add_files(
    files: List[UploadFile] = File(...),
    metadata: Optional[Any] = Form(...),
    collection_name: Optional[str] = Form(None),
    qdrant_crud: QdrantCRUD = Depends(get_qdrant_crud)):
    try:
        # Load metadata
        metadata = json.loads(metadata)
        if metadata is None:
            metadata = [{}] * len(files)
        elif isinstance(metadata, list):
            if len(metadata) != len(files):
                raise HTTPException(status_code=400, detail="Number of metadata entries should match the number of files.")
        elif isinstance(metadata, dict):
            metadata = [metadata]
        else:
            raise HTTPException(status_code=400, detail="Metadata should be a dictionary or a list of dictionaries.")
        # Load collection name from the request
        if collection_name:
            if not isinstance(collection_name, str):
                raise HTTPException(status_code=400, detail="collection_name must be a string.")
            collection_name = collection_name
        else:
            collection_name = config.vectordb.collection_name


        # Create a temporary directory to store files
        save_dir = Path(DATA_DIR) / collection_name
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Save the uploaded files
        for i, file in enumerate(files):
            file_path = save_dir / Path(file.filename).name
            logger.info(f"Processing file: {file.filename} and saving to {file_path}")
            with open(file_path, "wb") as buffer:
                buffer.write(await file.read())
            # Now pass the file path to the Indexer
            await qdrant_crud.add_files(path=file_path, metadata=metadata[i], collection_name=collection_name)

        return JSONResponse(content={"message": f"Files processed and added to the vector database : {[file.filename for file in files]}"}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search/", response_model=None)
async def search(query_params: SearchRequest, qdrant_crud: QdrantCRUD = Depends(get_qdrant_crud)):
    try:
        # Extract query and top_k from request
        query = query_params.query
        top_k = query_params.top_k
        collection_name = query_params.collection_name if query_params.collection_name else config.vectordb.collection_name
        logger.info(f"Searching for query: {query} in collection: {collection_name}")
        # Perform the search using the Indexer
        results = await qdrant_crud.search(query, top_k, collection_name)
        
        # Transforming the results (assuming they are LangChain documents)
        documents = [{"page_content": doc.page_content, "metadata": doc.metadata} for doc in results]
        
        # Return results
        return JSONResponse(content={f"Results in collection {collection_name}": documents}, status_code=200)

    except Exception as e:
        # Handle errors
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete-files/",response_model=None)
async def delete_files(request : DeleteFilesRequest, qdrant_crud: QdrantCRUD = Depends(get_qdrant_crud)):
    """
    Delete points in Qdrant associated with the given file names.

    Args:
        file_names (List[str]): A list of file names whose points are to be deleted.

    Returns:
        JSONResponse: A confirmation message including details of files processed.
    """

    try:
        collection_name = request.collection_name if request.collection_name else config.vectordb.collection_name
        deleted_files, not_found_files = qdrant_crud.delete_files(request.file_names, collection_name)
        return {
            "message": "File processing completed.",
            "files_deleted": deleted_files,
            "files_not_found": not_found_files,
        }

    except Exception as e:
        # Handle errors
        raise HTTPException(status_code=500, detail=str(e))