import os
from typing import Type, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from supabase import create_client, Client as SupabaseClient
from dotenv import load_dotenv
import logging
import json # Importar json para serializar o dicionário de retorno

logger = logging.getLogger(__name__)
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") # Usar la service_role key para acceso directo

class SupabaseDocumentContentSchema(BaseModel):
    """Input schema for SupabaseDocumentContentTool."""
    document_name: str = Field(description="The exact name of the document (e.g., 'checklist.pdf', '1- CNPJ.pdf') to retrieve from the 'documents' table in Supabase.")
    case_id: str = Field(description="The case ID associated with the document, used for filtering.")

class SupabaseDocumentContentTool(BaseTool):
    name: str = "Supabase Document Info Retriever"
    description: str = "Retrieves metadata, including the file URL, name, and document_tag, for a specific document stored in the 'documents' table in Supabase, filtered by its name and case_id. Returns a JSON string with this information."
    args_schema: Type[BaseModel] = SupabaseDocumentContentSchema
    supabase_client: Optional[SupabaseClient] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            logger.error("Supabase URL ou Service Key não configurados nas variáveis de ambiente.")
            raise ValueError("Supabase URL or Service Key not configured for SupabaseDocumentContentTool.")
        try:
            self.supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            logger.info("Cliente Supabase inicializado para SupabaseDocumentContentTool.")
        except Exception as e:
            logger.error(f"Falha ao inicializar cliente Supabase para SupabaseDocumentContentTool: {e}")
            self.supabase_client = None # Garantir que está None se falhar

    def _run(self, document_name: str, case_id: str) -> str:
        if not self.supabase_client:
            return "Error: Supabase client not initialized."
        try:
            logger.info(f"Recuperando informações para o documento: '{document_name}' com case_id: '{case_id}' da tabela 'documents'.")
            response = (
                self.supabase_client.table("documents")
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
                    # Preparar o dicionário com as informações
                    result_data = {
                        "file_url": file_url,
                        "document_name": doc_info.get("name"),
                        "document_tag": doc_info.get("document_tag")
                    }
                    logger.info(f"Informações encontradas para '{document_name}' (case_id: '{case_id}'): {result_data}")
                    return json.dumps(result_data) # Retornar como string JSON
                else:
                    logger.warning(f"Documento '{document_name}' (case_id: '{case_id}') encontrado mas não possui file_url.")
                    return f"Error: Document '{document_name}' (case_id: '{case_id}') found but has no file_url."
            else:
                logger.warning(f"Nenhum documento encontrado com o nome '{document_name}' e case_id '{case_id}' na tabela 'documents'.")
                return f"Error: No document found with name '{document_name}' and case_id '{case_id}'."

        except Exception as e:
            logger.error(f"Erro ao consultar a tabela 'documents' no Supabase para '{document_name}' (case_id: '{case_id}'): {e}")
            return f"Error querying Supabase for document '{document_name}' (case_id: '{case_id}'): {str(e)}"

# Exemplo de uso (para teste local, se necessário):
# if __name__ == '__main__':
#     # Certifique-se que SUPABASE_URL e SUPABASE_SERVICE_KEY estão no seu .env
#     tool = SupabaseDocumentContentTool()
#     # Substitua pelo nome de um documento e case_id que existam na sua tabela
#     doc_name_to_test = "4- CONTRATO SOCIAL AD PRODUTOS E SERVIÇOS.pdf" 
#     case_id_to_test = "CASO-CLIENTE-REAL-001"
#     info = tool._run(document_name=doc_name_to_test, case_id=case_id_to_test)
#     print(f"Informações para '{doc_name_to_test}' (case_id: '{case_id_to_test}'):\n{info}")
#     # Teste com um documento que não existe
#     # info_not_found = tool._run(document_name="naoexiste.pdf", case_id="CASO-TESTE-000")
#     # print(f"Resultado para documento não existente: {info_not_found}")
#     # Teste com um documento que existe mas não tem file_url (se aplicável)
#     # ... (necessitaria de um registro de teste sem file_url) 