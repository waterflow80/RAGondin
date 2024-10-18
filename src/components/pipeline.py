from pathlib import Path
import sys
from .chunker import BaseChunker, CHUNKERS
from langchain_core.documents.base import Document
from .llm import LLM
from .utils import format_context, load_sys_template
from .reranker import Reranker
from .retriever import BaseRetriever, get_retriever
from .vector_store import CONNECTORS
from .embeddings import HFEmbedder
from .config import Config
from .loader import GeneralLoader
from loguru import logger
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import (
    MessagesPlaceholder, 
    ChatPromptTemplate
)
from langchain_core.messages import (
    AIMessage, 
    HumanMessage
)
from collections import deque



dir_path = Path(__file__).parent


class Indexer:
    """This class bridges static files with the vector store database.
    """
    def __init__(self, config: Config, logger, device=None) -> None:
        # init the embedder model
        embedder = HFEmbedder(config, device=device)

        # init chunker 
        chunker_params = dict(config.chunker)
        name = chunker_params.pop("name")
        for k, v in chunker_params.items():
            try:
                chunker_params[k] = int(v)
            except: pass

        if name.startswith("semantic_splitter"):    
            chunker_params.update({"embeddings": embedder.get_embeddings()})

        self.chunker: BaseChunker = CHUNKERS[name](**chunker_params)

        # init the connector
        dbconfig = config.vectordb
        self.connector = CONNECTORS[dbconfig["connector_name"]](
            host=dbconfig["host"],
            port=dbconfig["port"],
            collection_name=dbconfig["collection_name"],
            embeddings=embedder.get_embeddings(), 
            hybrid_mode=bool(dbconfig['hybrid_mode']),
            logger=logger
        )
        self.logger = logger
        self.logger.info("Indexer initialized...")


    async def add_files2vdb(self, path):
        """Add a files to the vector database in async mode"""
        docs = GeneralLoader(batch_size=6)
        try:
            docs_gen = docs.doc_generator(path)
            batch_gen = self.chunker.split(docs_gen)
            await self.connector.async_add_documents(batch_gen)
            self.logger.info(f"Documents from {path} added.")
        except Exception as e:
            raise Exception(f"An exception as occured: {e}")


class RagPipeline:
    def __init__(self, config: Config, device="cpu") -> None:
        self.config = config
        self.logger = self.set_logger(config)
        self.indexer = Indexer(config, self.logger, device=device)
            
        self.reranker = None
        if config.reranker["model_name"]:
            self.reranker = Reranker(self.logger, config)
        self.reranker_top_k = int(config.reranker["top_k"])

        self.qa_sys_prompt: ChatPromptTemplate = load_sys_template(
            config.dir_path / "prompts/rag_sys_prompt_template.txt"
        )

        self.llm_client = LLM(config, logger)
        self.retriever: BaseRetriever = get_retriever(config, logger)

        self.rag_mode = config.rag["mode"]
        self.chat_history_depth = int(config.rag["chat_history_depth"])
        self._chat_history: deque = deque(maxlen=self.chat_history_depth)

    def get_contextualize_docs(self, question: str, chat_history: list)-> list[Document]:
        """With this function, the new question is reformulated as a standalone question that takes into account the chat_history.
        The new contextualized question is better suited for retreival. 
        This contextualisation allows to have a RAG agent that also takes into account history, so chatbot RAG.

        Args:
            `question` (str): The user question
            `chat_history` (list): The conversation history
        """        
        if self.rag_mode == "SimpleRag": # for the SimpleRag, we don't need the contextualize as questions are treated independently regardless of the chat_history
            logger.info("Documents retreived...")
            docs = self.retriever.retrieve(
                question, 
                db=self.indexer.connector
            )

        if self.rag_mode == "ChatBotRag":
            logger.info("Contextualizing the question")
            
            sys_prompt = load_sys_template(
                dir_path / "prompts/contextualize_prompt_template.txt" # get the prompt for contextualizing
            )
            contextualize_q_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", sys_prompt),
                    MessagesPlaceholder("chat_history"),
                    ("human", "Here is the question to contextualize: '{input}'"),
                ]
            )
            history_aware_retriever = (
                contextualize_q_prompt
                | self.llm_client.client
                | StrOutputParser()
            )

            input_ = {"input": question, "chat_history": chat_history}

            logger.info("Generating contextualized question for retreival...") 
            contextualized_question = history_aware_retriever.invoke(input_) # TODO: this is the bootleneck, the model answers sometimes instead of reformulating  
            print("==>", contextualized_question)
            logger.info("Documents retreived...")

            docs = self.retriever.retrieve(
                contextualized_question, 
                db=self.indexer.connector
            )

        return docs 
    

    def run(self, question: str="", chat_history_api: list[AIMessage | HumanMessage] = None):
        if chat_history_api is None: 
            chat_history = list(self._chat_history) # use the saved chat history
        else:
            # this is for when the user provides chat_history (in api_mode)
            chat_history = chat_history[self.chat_history_depth:]

        # 1. contextualize the question and retreive relevant documents
        docs = self.get_contextualize_docs(question, chat_history) 

        # 2. rerank documents is asked
        if self.reranker is not None:
            docs = self.reranker.rerank(question, docs=docs, k=self.reranker_top_k)
        
        # 3. Format the retrieved docs
        context, sources = format_context(docs)

        # 4. run the llm for inference
        answer = self.llm_client.run(
            question=question, 
            chat_history=chat_history,
            context=context, sys_pmpt_tmpl=self.qa_sys_prompt)

        return answer, context, sources, docs

    
    def update_history(self, question: str, answer: str):
        self._chat_history.extend(
            [
                HumanMessage(content=question),
                AIMessage(content=answer),
            ]
        )
    
    @staticmethod
    def set_logger(config):
        verbose = config.verbose
        if bool(verbose["verbose"]):
            level = verbose['level']
        else:
            level = 'ERROR'
        logger.remove()
        logger.add(sys.stderr, level=level)
        return logger