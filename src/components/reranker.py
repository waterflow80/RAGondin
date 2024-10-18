from ragatouille import RAGPretrainedModel
from loguru import logger
from langchain_core.documents.base import Document


class Reranker:
    """Reranks documents for a query using a RAG model."""

    def __init__(self, logger, config):
        """
        Initialize Reranker.

        Args:
            model_name (str): Name of pretrained RAGondin model to use.
        """
        self.model = RAGPretrainedModel.from_pretrained(
            config.reranker["model_name"]
        )
        self.logger = logger
        self.logger.info("Reranker initialized...")

    def rerank(self, question: str, docs: list[Document], k: int = 5) -> list[Document]:
        logger.info("Reranking documents ...")
        """
        Rerank documents by relevancy with respect to the given query.

        Args:
            question (str): Search query.
            docs (list[str]): List of document strings.
            k (int): Number of documents to return.

        Returns:
            list[str]: Top k reranked document strings.
        """
        docs_unique = [doc for doc in drop_duplicates(docs, self.logger)]
        k = min(k, len(docs_unique)) # k must be <= the number of documents
        ranked_txt = self.model.rerank(question, [d.page_content for d in docs_unique], k=k)
        ranked_docs = original_docs(ranked_txt, docs_unique)
        return [doc for doc in ranked_docs]
    

def original_docs(ranked_txt, docs: list[Document]):
    for doc_txt in ranked_txt:
        for doc in docs:
            if doc_txt["content"] == doc.page_content:
                yield doc
                docs.remove(doc)
                break


def drop_duplicates(L: list[Document], logger, key=None):
    seen = set()
    for s in L:
        val = s.page_content if key is None else key(s)
        if val not in seen:
            seen.add(val)
            yield s
        else:
            logger.info("Duplicata removed...")


if __name__ == "__main__":
    q = 'Comment vas-tu?'
    resp = ["je n'y comprends rien", "je n'aime pas la politique", "je vais bien",  "la bonne communication"]
    reranker = Reranker()
    print(reranker.model.rerank(q, resp, k=3))