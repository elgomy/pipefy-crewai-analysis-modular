import os
import tempfile
import asyncio
import httpx # Usado para baixar arquivos de URLs
from typing import Type, Optional, Literal, List, Any, Union
from pydantic import BaseModel, Field, validator # MODIFICADO: Usar pydantic (V2)
try:
    from crewai.tools import BaseTool
except ImportError:
    # Fallback para versiones más nuevas de CrewAI
    from crewai.tools.base_tool import BaseTool
from dotenv import load_dotenv
# import llamacloud # Removido - não é necessário, já que usamos llama_parse diretamente
import logging # Adicionado para o logger que já existe

# Certifique-se de instalar: pip install crewai-tools llama-parse httpx pydantic llama-index-core
# llama-parse é a biblioteca específica para o serviço LlamaParse
from llama_parse import LlamaParse
try:
    from llama_index.core.schema import Document # LlamaParse retorna objetos Document do LlamaIndex
except ImportError:
    # Fallback para versões mais antigas
    try:
        from llama_index.schema import Document
    except ImportError:
        # Se não conseguir importar, criar uma classe simples
        class Document:
            def __init__(self, text: str = "", **kwargs):
                self.text = text

# Configuração básica de logging para a ferramenta
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente. É bom ter isso no início do módulo.
load_dotenv()
LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")

# Definindo os tipos de preset permitidos, alinhados com ParsingMode
# O usuário mencionou "fast", "balanced", "detailed".
# ParsingMode tem SIMPLE e DETAILED.
# Mapearemos "fast" e "balanced" para SIMPLE, e "detailed" para DETAILED.
ParsingPreset = Literal["simple", "detailed"]

class LlamaParseDirectToolSchema(BaseModel):
    """Input schema for LlamaParseDirectTool (Pydantic V2)."""
    document_url: Optional[str] = Field(
        default=None, # Pydantic V2: default primeiro
        description="URL do documento a ser processado. Um entre document_url ou file_path deve ser fornecido."
    )
    file_path: Optional[str] = Field(
        default=None, 
        description="Caminho local do arquivo a ser processado. Um entre document_url ou file_path deve ser fornecido."
    )
    parsing_instructions: Optional[str] = Field(
        default=None, 
        description="Instruções específicas para o parseamento, por exemplo, para focar em tabelas ou texto."
    )
    language: Optional[str] = Field(
        default="pt", 
        description="Idioma do documento (padrão: 'pt' para português). Use códigos ISO 639-1."
    )
    result_as_markdown: Optional[bool] = Field(
        default=True,
        description="Se o resultado deve ser retornado como Markdown (padrão: True)."
    )
    parsing_preset: Optional[ParsingPreset] = Field(
        default="simple",
        description="Preset de parseamento a ser usado ('simple' ou 'detailed', padrão: 'simple')."
    )

    # Para Pydantic V2, a validação cruzada é feita com model_validator
    # from pydantic import model_validator
    # @model_validator(mode='before') # ou 'after'
    # def check_document_source_v2(cls, data: Any) -> Any:
    #     if isinstance(data, dict):
    #          if not data.get('document_url') and not data.get('file_path'):
    #              raise ValueError('LlamaParseDirectToolSchema: Either document_url or file_path must be provided.')
    #     elif hasattr(data, 'document_url') and hasattr(data, 'file_path'): # se for um objeto já validado parcialmente
    #          if not data.document_url and not data.file_path:
    #              raise ValueError('LlamaParseDirectToolSchema: Either document_url or file_path must be provided.')
    #     return data
    # Por simplicidade, esta validação pode ser feita no método _run da ferramenta se necessário.

class LlamaParseDirectTool(BaseTool):
    name: str = "LlamaParse Direct Document Parser"
    description: str = (
        "Processa um documento (PDF, etc.) diretamente via URL ou caminho de arquivo usando LlamaParse da LlamaCloud "
        "para extrair seu conteúdo como markdown. Ideal para obter o texto de documentos para análise."
    )
    args_schema: Type[BaseModel] = LlamaParseDirectToolSchema
    api_key: Optional[str] = None
    _sync_parser: Optional[LlamaParse] = None # Para cache da instância síncrona

    def __init__(self, llama_cloud_api_key: Optional[str] = None, **kwargs: Any):
        super().__init__(**kwargs)
        resolved_api_key = llama_cloud_api_key or LLAMA_CLOUD_API_KEY
        if not resolved_api_key:
            logger.error("LLAMA_CLOUD_API_KEY não foi encontrada nas variáveis de ambiente nem fornecida diretamente.")
            raise ValueError("LLAMA_CLOUD_API_KEY não configurada para LlamaParseDirectTool.")
        self.api_key = resolved_api_key
        
        # Removida a inicialização do self.client = llamacloud.LlamaCloud(...)
        # A instância de LlamaParse (de llama_parse) será criada sob demanda.

    async def _download_file_if_url(self, file_path_or_url: str) -> str:
        """Downloads a file from a URL to a temporary local path if it's a URL."""
        # A lógica parece correta, mantida como está (com pequena correção de nome de var)
        if file_path_or_url.startswith("http://") or file_path_or_url.startswith("https://"):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(file_path_or_url)
                    response.raise_for_status()
                
                possible_extension = ""
                if '.' in file_path_or_url.split('/')[-1]:
                    possible_extension = "." + file_path_or_url.split('/')[-1].split('.')[-1]

                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=possible_extension, mode='wb') # mode='wb' para binário
                temp_file.write(response.content)
                temp_file.close()
                logger.info(f"Arquivo baixado de {file_path_or_url} para {temp_file.name}")
                return temp_file.name
            except httpx.HTTPStatusError as e:
                logger.error(f"Erro HTTP {e.response.status_code} ao baixar {file_path_or_url}: {e.response.text}")
                return f"Error downloading file: HTTP error {e.response.status_code}"
            except httpx.RequestError as e:
                logger.error(f"Erro de requisição ao baixar {file_path_or_url}: {e}")
                return f"Error downloading file: Request failed {e}"
            except Exception as e:
                logger.error(f"Erro inesperado ao baixar {file_path_or_url}: {e}")
                return f"An unexpected error occurred while downloading the file: {e}"
        return file_path_or_url

    def _get_parser_instance(self, preset: ParsingPreset, language: str, result_as_markdown: bool) -> LlamaParse:
        """Configura e retorna uma instância do LlamaParse parser."""
        api_key_to_use = self.api_key or LLAMA_CLOUD_API_KEY
        if not api_key_to_use:
            logger.error("LlamaCloud API Key não fornecida nem como argumento nem como variável de ambiente.")

        # Corrigir o código de idioma se for passado 'por'
        actual_language = "pt" if language.lower() == "por" else language

        # Usar strings diretamente para o modo, conforme a documentação de LlamaParse
        # sugere que "simple" ou "detailed" como strings são aceitáveis.
        mode_to_use_str = "detailed" if preset == "detailed" else "simple"

        return LlamaParse(
            api_key=api_key_to_use,
            result_type="markdown" if result_as_markdown else "text",
            language=actual_language,
            mode=mode_to_use_str # Usando o string diretamente
        )

    async def _arun_internal(
        self, 
        file_path_or_url: str, 
        parsing_preset: ParsingPreset, 
        parsing_instructions: Optional[str],
        language: str, 
        result_as_markdown: bool
    ) -> str:
        """Lógica assíncrona interna para parsear o documento."""
        if not self.api_key:
            return "Error: Llama Cloud API key not configured."

        actual_file_path = await self._download_file_if_url(file_path_or_url)
        if actual_file_path.startswith("Error:"): 
            return actual_file_path 

        try:
            logger.info(f"Parseando documento: {actual_file_path} com preset={parsing_preset}, lang={language}")
            parser = self._get_parser_instance(parsing_preset, language, result_as_markdown)

            documents: List[Document] = await parser.aload_data(actual_file_path)
            
            if not documents:
                logger.warning(f"LlamaParse não retornou documentos para {actual_file_path}.")
                return "LlamaParse did not return any documents."
            
            full_text = "\n\n---\n\n".join([doc.text for doc in documents if doc.text])
            logger.info(f"Parseamento de {actual_file_path} concluído. Tamanho do texto: {len(full_text)}")
            return full_text if full_text else "LlamaParse returned document(s) with no textual content."

        except FileNotFoundError:
            logger.error(f"Arquivo não encontrado em {actual_file_path} durante o parseamento.")
            return f"Error: File not found at {actual_file_path}"
        except Exception as e:
            logger.exception(f"Erro inesperado durante o processamento LlamaParse de {actual_file_path}: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'): # Para erros HTTP
                return f"Error during LlamaParse processing: {e.response.text} (Details: {str(e)})"
            return f"An unexpected error occurred during LlamaParse processing: {str(e)}"
        finally:
            if (file_path_or_url.startswith("http://") or file_path_or_url.startswith("https://")) and os.path.exists(actual_file_path) and tempfile.gettempdir() in os.path.abspath(actual_file_path):
                try:
                    os.remove(actual_file_path)
                    logger.info(f"Arquivo temporário {actual_file_path} removido.")
                except Exception as e_rm:
                    logger.warning(f"Não foi possível remover o arquivo temporário {actual_file_path}: {e_rm}")

    def _run(
        self, 
        document_url: Optional[str] = None,
        file_path: Optional[str] = None,
        parsing_preset: ParsingPreset = "simple", 
        parsing_instructions: Optional[str] = None,
        language: str = "pt", 
        result_as_markdown: bool = True
    ) -> str:
        """
        Synchronously parses a document (local file or URL) using LlamaParse.
        """
        if not document_url and not file_path:
            return "Error: Either document_url or file_path must be provided."
        
        source_path = document_url if document_url else file_path
        if source_path is None: # Checagem de segurança para o mypy
             return "Error: Document source path is None after check, unexpected error."

        logger.info(f"Iniciando parseamento síncrono para: {source_path}")
        
        actual_file_to_parse = source_path
        temp_file_path_for_cleanup: Optional[str] = None

        if source_path.startswith("http://") or source_path.startswith("https://"):
            logger.info(f"Baixando arquivo para execução síncrona: {source_path}")
            temp_file_obj = None
            try:
                with httpx.Client() as client: # Cliente síncrono
                    response = client.get(source_path)
                    response.raise_for_status()
                
                possible_extension = ""
                if '.' in source_path.split('/')[-1]:
                    possible_extension = "." + source_path.split('/')[-1].split('.')[-1]
                
                # Usar with para garantir o fechamento do arquivo temporário
                temp_file_obj = tempfile.NamedTemporaryFile(delete=False, suffix=possible_extension, mode='wb')
                temp_file_obj.write(response.content)
                actual_file_to_parse = temp_file_obj.name
                temp_file_path_for_cleanup = actual_file_to_parse # Guardar para limpeza
                temp_file_obj.close() # Fechar o arquivo para que LlamaParse possa abri-lo
                logger.info(f"Arquivo baixado para {actual_file_to_parse}")
            except Exception as e_dl_sync:
                logger.error(f"Erro ao baixar {source_path} sincronicamente: {e_dl_sync}")
                if temp_file_obj and os.path.exists(temp_file_obj.name):
                    try:
                        os.remove(temp_file_obj.name)
                    except Exception as e_rm_fail: 
                        logger.warning(f"Falha ao remover arquivo temporário após erro de download: {temp_file_obj.name}, erro: {e_rm_fail}")
                return f"Error downloading file synchronously: {e_dl_sync}"
        
        try:
            parser = self._get_parser_instance(parsing_preset, language, result_as_markdown)
            
            documents: List[Document] = parser.load_data(actual_file_to_parse) 
            if not documents:
                logger.warning(f"LlamaParse não retornou documentos para {actual_file_to_parse} (sync).")
                return "LlamaParse did not return any documents (sync)."
            
            full_text = "\n\n---\n\n".join([doc.text for doc in documents if doc.text])
            logger.info(f"Parseamento de {actual_file_to_parse} (sync) concluído. Tamanho do texto: {len(full_text)}")
            return full_text if full_text else "LlamaParse returned document(s) with no textual content (sync)."

        except FileNotFoundError:
            logger.error(f"Arquivo não encontrado em {actual_file_to_parse} durante o parseamento (sync).")
            return f"Error: File not found at {actual_file_to_parse} (sync)"
        except Exception as e_parse_sync:
            logger.exception(f"Erro durante parseamento síncrono de {actual_file_to_parse}: {e_parse_sync}")
            if hasattr(e_parse_sync, 'response') and hasattr(e_parse_sync.response, 'text'): # Para erros HTTP de LlamaParse
                 return f"Error during LlamaParse processing (sync): {e_parse_sync.response.text} (Details: {str(e_parse_sync)})"
            return f"An unexpected error occurred during synchronous LlamaParse processing: {e_parse_sync}"
        finally:
            if temp_file_path_for_cleanup and os.path.exists(temp_file_path_for_cleanup):
                try:
                    os.remove(temp_file_path_for_cleanup)
                    logger.info(f"Arquivo temporário {temp_file_path_for_cleanup} removido (sync).")
                except Exception as e_rm_sync:
                    logger.warning(f"Não foi possível remover o arquivo temporário {temp_file_path_for_cleanup} (sync): {e_rm_sync}")

    async def _arun(
        self, 
        document_url: Optional[str] = None,
        file_path: Optional[str] = None,
        parsing_preset: ParsingPreset = "simple",
        parsing_instructions: Optional[str] = None,
        language: str = "pt", 
        result_as_markdown: bool = True
    ) -> str:
        """
        Asynchronously parses a document (local file or URL) using LlamaParse.
        """
        if not document_url and not file_path:
            return "Error: Either document_url or file_path must be provided."
        
        source_path = document_url if document_url else file_path
        if source_path is None: # Checagem de segurança para o mypy
            return "Error: Document source path is None after check, unexpected error."

        logger.info(f"Iniciando parseamento assíncrono para: {source_path}")
        return await self._arun_internal(
            file_path_or_url=source_path, 
            parsing_preset=parsing_preset, 
            parsing_instructions=parsing_instructions,
            language=language, 
            result_as_markdown=result_as_markdown
        )

# Exemplo de como testar a ferramenta (opcional, pode ser removido ou movido para testes)
async def main_async_test():
    print("Testando LlamaParseDirectTool...")
    # Certifique-se de ter LLAMA_CLOUD_API_KEY no seu .env
    tool = LlamaParseDirectTool()

    # Teste com URL (substitua por uma URL de PDF real e publicamente acessível)
    # Exemplo: um PDF pequeno da web
    # test_url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
    # print(f"\nTestando com URL: {test_url}")
    # result_url = await tool._arun(document_url=test_url, parsing_instructions="Extraia o título.")
    # print(f"Resultado URL:\n{result_url}")

    # Teste com arquivo local (crie um dummy.pdf ou use um PDF pequeno)
    # Crie um arquivo dummy.pdf no mesmo diretório para teste
    # if not os.path.exists("dummy.pdf"):
    #     with open("dummy.pdf", "w") as f:
    #         f.write("%PDF-1.4\n%âãÏÓ\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000015 00000 n\n0000000060 00000 n\n0000000117 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF")
    
    # print(f"\nTestando com arquivo local: dummy.pdf")
    # result_local = await tool._arun(file_path="dummy.pdf", parsing_instructions="Qual o conteúdo principal?")
    # print(f"Resultado Local:\n{result_local}")

    # Teste síncrono (via _run)
    # print(f"\nTestando _run com arquivo local: dummy.pdf")
    # result_sync_local = tool._run(file_path="dummy.pdf")
    # print(f"Resultado _run Local:\n{result_sync_local}")

if __name__ == "__main__":
    # Para rodar o teste async:
    # asyncio.run(main_async_test())
    
    # Para testar o _run diretamente (se não houver loop de evento rodando)
    # tool = LlamaParseDirectTool()
    # print(tool._run(file_path="dummy.pdf"))
    pass 