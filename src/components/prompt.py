from langchain.prompts import PromptTemplate
from .llm import LLM
from pathlib import Path
from pathlib import Path
from langchain_core.documents.base import Document


dir_path = Path(__file__).parent

class BasicPrompt:
    """Class for generating prompts to provide context for LLMs."""
    def __init__(
            self, 
            prompt_file: str = dir_path / "prompts/basic_prompt_template.txt"
        ) -> None:
        
        self.msg_templates = get_msgs(prompt_file)

    def get_prompt(self, question: str, docs: list[Document] = None) -> tuple[dict, str]:
        context = _build_context(docs)
        sys_template, user_template = self.msg_templates

        sys_prompt = sys_template
        user_prompt = user_template.format(
            question=question, 
            context=context
        )


        return [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ], context
        
class MultiQueryPrompt(BasicPrompt):
    def __init__(
            self, 
            prompt_file: str = dir_path / "prompts/multi_query_prompt_template.txt",
        ) -> None:
        super().__init__(prompt_file)
    
    def get_multi_query_prompt(self, question: str, k_queries: int) -> dict:
        sys_template, user_template = self.msg_templates
        sys_prompt = sys_template.format(k=str(k_queries))
        user_prompt = user_template.format(question=question)
        return [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]
    


PROMPT_TEMPLATES = {
    "basic": BasicPrompt,
    "multiQuery": MultiQueryPrompt
}   

def get_msgs(file_path: Path) -> tuple[str, str]:
    with open(file_path, mode="r") as f:
        txt = f.read()
        sys_msg, user_msg = txt.split("&&&\n")
        return sys_msg, user_msg

def _build_context(docs: list[Document]) -> str:
    """Build context string from list of documents."""
    #TODO: Add links to used document and specify to the model (in the prompt) to use them for referencing.
    context = "Extracted documents:"
    for i, doc in enumerate(docs, start=1):
        context += f"""
        Source {i} : {doc.metadata["source"]}#page={doc.metadata["page"]+1}
        Content : {doc.page_content}
        =======\n
        """
    return context

def generate_multi_query(llm: LLM, msg_prompts: dict) -> list[str]:
    questions = llm.run(msg_prompts)
    questions = questions.split("####Generated Questions: ")[-1]
    questions_l = questions.split("[SEP]")
    return questions_l