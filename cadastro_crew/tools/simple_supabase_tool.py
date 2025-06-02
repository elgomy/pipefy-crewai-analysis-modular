import os
import json
import logging
from supabase import create_client
from dotenv import load_dotenv
from crewai.tools import tool

logger = logging.getLogger(__name__)
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

@tool("Supabase Document Info Retriever")
def get_supabase_document_info(document_name: str, case_id: str) -> str:
    """Retrieves metadata, including the file URL, name, and document_tag, for a specific document stored in the 'documents' table in Supabase, filtered by its name and case_id. Returns a JSON string with this information."""
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("Supabase URL ou Service Key não configurados nas variáveis de ambiente.")
        return "Error: Supabase URL or Service Key not configured."
    
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logger.info(f"Recuperando informações para o documento: '{document_name}' com case_id: '{case_id}' da tabela 'documents'.")
        
        response = (
            supabase_client.table("documents")
            .select("file_url, name, document_tag")
            .eq("name", document_name)
            .eq("case_id", case_id)
            .limit(1)
            .execute()
        )
        
        if response.data:
            doc_info = response.data[0]
            file_url = doc_info.get("file_url")
            
            if file_url:
                result_data = {
                    "file_url": file_url,
                    "document_name": doc_info.get("name"),
                    "document_tag": doc_info.get("document_tag")
                }
                logger.info(f"Informações encontradas para '{document_name}' (case_id: '{case_id}'): {result_data}")
                return json.dumps(result_data)
            else:
                logger.warning(f"Documento '{document_name}' (case_id: '{case_id}') encontrado mas não possui file_url.")
                return f"Error: Document '{document_name}' (case_id: '{case_id}') found but has no file_url."
        else:
            logger.warning(f"Nenhum documento encontrado com o nome '{document_name}' e case_id '{case_id}' na tabela 'documents'.")
            return f"Error: No document found with name '{document_name}' and case_id '{case_id}'."

    except Exception as e:
        logger.error(f"Erro ao consultar a tabela 'documents' no Supabase para '{document_name}' (case_id: '{case_id}'): {e}")
        return f"Error querying Supabase for document '{document_name}' (case_id: '{case_id}'): {str(e)}" 