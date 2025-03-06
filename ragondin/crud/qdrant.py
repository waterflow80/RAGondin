from components import Indexer
from config import load_config
from qdrant_client import models
from typing import List, Optional, Union, Dict
from loguru import logger

# Load the configuration
config = load_config()

class QdrantCRUD :
    def __init__(self, indexer: Indexer = Indexer(config=config, logger=logger)):
        self.indexer = indexer
        self.collection_name = config.vectordb.collection_name
        self.logger = self.indexer.logger

    async def add_files(self, path: str, metadata: Optional[Dict], collection_name : Optional[str] = None):
        """
        Add files to Qdrant
        """
        try:
            await self.indexer.add_files2vdb(path=path, metadata=metadata, collection_name=collection_name)
        except Exception as e:
            self.logger.error(f"Couldn't add directory {path} to Qdrant : {e}")
            raise
        
    async def search(self, query: str, top_k: int, collection_name : Optional[str] = None):
        return await self.indexer.vectordb.async_search(query, top_k, collection_name=collection_name)


    def get_file_points(self, filter: dict, collection_name):
        """
        Get the points associated with a file from Qdrant
        """
        try:
            # Scroll through all vectors
            has_more = True
            offset = None
            results = []

            key = next(iter(filter))
            value = filter[key]

            while has_more:
                response = self.indexer.vectordb.client.scroll(
                    collection_name=collection_name if collection_name else self.collection_name,
                    scroll_filter=models.Filter(must=[models.FieldCondition(key=f"metadata.{key}",match=models.MatchValue(value=value))]),
                    limit=100,
                    offset=offset,
                )
                
                # Add points that contain the filename in metadata.source
                results.extend(response[0])
                has_more = response[1]  # Check if there are more results
                offset = response[1] if has_more else None

            # Return list of result ids
            return [res.id for res in results]
        
        except Exception as e:
            self.logger.error(f"Couldn't get file points for {key} {value}: {e}")
            raise


    def delete_points(self, points: list, collection_name: Optional[str] = None):
        """
        Delete points from Qdrant
        """
        try:
            self.indexer.vectordb.client.delete(
                collection_name=collection_name if collection_name else self.collection_name,
                points_selector=models.PointIdsList(points=points)
            )
        except Exception as e:
            self.logger.error(f"Error in `delete_points`: {e}")
    
    def delete_files(self, filters: Union[Dict, List[Dict]], collection_name: Optional[str] = None):
        deleted_files = []
        not_found_files = []


        for filter in filters:
            try:
                key = next(iter(filter))
                value = filter[key]
                # Get points associated with the file name
                points = self.get_file_points(filter, collection_name)
                if not points:
                    self.logger.info(f"No points found for {key}: {value}")
                    not_found_files.append(filter)
                    continue

                # Delete the points
                self.delete_points(points, collection_name)
                deleted_files.append(filter)

            except Exception as e:
                self.logger.error(f"Error in `delete_files` for {key} {value}: {e}")
        
        return deleted_files, not_found_files


    def file_exists(self, file_name: str, collection_name: Optional[str] = None):
        """
        Check if a file exists in Qdrant
        """
        try:
            # Get points associated with the file name
            points = self.get_file_points({"file_name": file_name}, collection_name)
            return True if points else False
        except Exception as e:
            self.logger.error(f"Error in `file_exists` for {file_name}: {e}")
            return False

    def update_file ():
        pass
        