from components import Indexer
from config import load_config
from pymilvus import Collection, utility
from typing import List
from loguru import logger

# Load the configuration
config = load_config()

class MilvusCRUD:
    def __init__(self, indexer: Indexer = Indexer(config=config, logger=logger)):
        self.indexer = indexer
        self.collection_name = config.vectordb.collection_name
        self.logger = self.indexer.logger
        self.collection = Collection(self.collection_name)

    async def add_files(self, path: str):
        """
        Add files to Milvus
        """
        try:
            await self.indexer.add_files2vdb(path=path)
        except Exception as e:
            self.logger.error(f"Couldn't add directory {path} to Milvus: {e}")
            raise
        
    async def search(self, query: str, top_k: int):
        return await self.indexer.vectordb.async_search(query, top_k)

    def get_file_points(self, file_name: str):
        """
        Get the points associated with a file from Milvus
        """
        try:
            # Scroll through all vectors
            has_more = True
            offset = 0
            limit = 100
            results = []

            while has_more:
                response = self.collection.query(
                    expr=f"metadata.source like '%{file_name}%'",
                    offset=offset,
                    limit=limit,
                    output_fields=["id", "metadata"]
                )
                
                # Add points that contain the filename in metadata.source
                results.extend(
                    point
                    for point in response
                    if file_name in point.get("metadata", {}).get("source", "")
                )
                has_more = len(response) == limit
                offset += limit

            # Return list of result ids
            return [res["id"] for res in results]
        
        except Exception as e:
            self.logger.error(f"Couldn't get file points for file {file_name}: {e}")
            raise

    def delete_points(self, points: list):
        """
        Delete points from Milvus
        """
        try:
            self.collection.delete(
                expr=f"id in {points}"
            )
        except Exception as e:
            self.logger.error(f"Error in `delete_points`: {e}")
    
    def delete_files(self, file_names: List[str]):
        deleted_files = []
        not_found_files = []

        for file_name in file_names:
            try:
                # Get points associated with the file name
                points = self.get_file_points(file_name)
                print(file_name, len(points))
                if not points:
                    self.logger.info(f"No points found for file: {file_name}")
                    not_found_files.append(file_name)
                    continue

                # Delete the points
                self.delete_points(points)
                deleted_files.append(file_name)

            except Exception as e:
                self.logger.error(f"Error in `delete_files` for file {file_name}: {e}")
        
        return deleted_files, not_found_files

    def update_file(self):
        pass