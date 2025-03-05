from pydantic import BaseModel
from typing import Optional, List, Dict, Union

class SearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5  # default to 5 if not provided
    collection_name: Optional[str] = None


class DeleteFilesRequest(BaseModel):
    file_names: List[str]
    collection_name: Optional[str] = None