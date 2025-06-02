import os
from typing import Type, Optional
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
from supabase import create_client, Client as SupabaseClient
from dotenv import load_dotenv
import logging
import numpy as np

# Dependências para a Knowledge Base (exemplo com Supabase/pgvector e SentenceTransformers)
# pip install supabase sentence-transformers
# Lembre-se de configurar o Supabase e a extensão pgvector

# --- Configuração da Knowledge Base (Supabase) ---
# REMOVER a leitura de variáveis de ambiente daqui
# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") 
KB_TABLE_NAME_DEFAULT = "knowledge_base_chunks"
EMBEDDING_MODEL_NAME_DEFAULT = "sentence-transformers/all-MiniLM-L6-v2"

logger = logging.getLogger(__name__)

# Intentar importar BaseTool, con fallback al decorador @tool
try:
    from crewai.tools import BaseTool
    BASETOOL_AVAILABLE = True
    logger.info("✅ BaseTool importado correctamente desde crewai.tools")
except ImportError:
    try:
        from crewai.tools.base_tool import BaseTool
        BASETOOL_AVAILABLE = True
        logger.info("✅ BaseTool importado desde crewai.tools.base_tool (ubicación alternativa)")
    except ImportError:
        logger.warning("⚠️ BaseTool no disponible, usando decorador @tool como fallback")
        BASETOOL_AVAILABLE = False
        try:
            from crewai.tools import tool
        except ImportError:
            logger.error("❌ Ni BaseTool ni @tool están disponibles")
            raise ImportError("CrewAI tools no disponibles")

class KnowledgeBaseQueryToolSchema(BaseModel):
    """Define os argumentos para a ferramenta de consulta à Knowledge Base (Pydantic V2)."""
    query: str = Field(description="A pergunta ou termo de busca em linguagem natural para consultar a base de conhecimento.")
    top_k: int = Field(default=3, description="O número de resultados mais relevantes a serem retornados.")
    # Poderia adicionar filtros aqui, ex: filter_metadata: Optional[dict] = Field(default=null, description="Metadados para filtrar a busca.")

def _run_kb_query(query: str, top_k: int = 3) -> str:
    """Función auxiliar para ejecutar la consulta a la Knowledge Base."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")
    kb_table_name = os.getenv("KB_TABLE_NAME", KB_TABLE_NAME_DEFAULT)
    embedding_model_name = os.getenv("EMBEDDING_MODEL_NAME", EMBEDDING_MODEL_NAME_DEFAULT)

    if not supabase_url or not supabase_service_key:
        return "ERRO: Variáveis SUPABASE_URL ou SUPABASE_SERVICE_KEY não configuradas."

    if not query:
        return "ERRO: A query para a Knowledge Base não pode ser vazia."
    
    if not kb_table_name:
        return "ERRO: Nome da tabela da Knowledge Base (KB_TABLE_NAME) não configurado."

    logger.info(f"INFO (KnowledgeBaseQueryTool): Recebida query para KB: '{query}', top_k={top_k}")

    try:
        # Inicializar cliente Supabase
        supabase_client = create_client(supabase_url, supabase_service_key)
        logger.info("INFO: Cliente Supabase inicializado para a KnowledgeBaseQueryTool.")
        
        # Inicializar modelo de embedding
        embedding_model = SentenceTransformer(embedding_model_name)
        logger.info(f"INFO: Modelo de embedding '{embedding_model_name}' carregado para KnowledgeBaseQueryTool.")

        # 1. Gerar embedding para a query
        logger.info("INFO: Gerando embedding para a query...")
        query_embedding = embedding_model.encode(query).tolist()
        logger.info("INFO: Embedding da query gerado.")

        # 2. Consultar Supabase usando uma função RPC (stored procedure) para busca de similaridade
        rpc_name = "match_kb_chunks" # Ou o nome que você der à sua função no Supabase

        logger.info(f"INFO: Executando RPC '{rpc_name}' no Supabase...")
        response = supabase_client.rpc(
            rpc_name,
            params={
                'query_embedding': query_embedding,
                'match_threshold': 0.5,  # Ajuste este limiar conforme necessário
                'match_count': top_k
            }
        ).execute()

        if response.data:
            logger.info(f"INFO: {len(response.data)} resultados encontrados na KB.")
            # Formatar os resultados
            formatted_results = []
            for i, item in enumerate(response.data):
                result_text = f"Resultado {i+1} (Similaridade: {item.get('similarity', 'N/A'):.4f}):\n"
                result_text += f"Conteúdo: {item.get('content', 'Conteúdo não disponível')}\n"
                if item.get('metadata'):
                    result_text += f"Metadados: {item.get('metadata')}\n"
                result_text += "---\n"
                formatted_results.append(result_text)
            
            if not formatted_results:
                return "INFO: Nenhum resultado relevante encontrado na Knowledge Base para esta query."
            return "\n".join(formatted_results)
        else:
            # Isso pode acontecer se a RPC não retornar dados ou se houver um erro na RPC não capturado como exceção HTTP
            logger.warning("ALERTA: Nenhum dado retornado pela RPC do Supabase, ou a resposta não continha 'data'.")
            if hasattr(response, 'error') and response.error:
                logger.error(f"ERRO RPC Supabase: {response.error}")
                return f"ERRO ao consultar KB: {response.error.message}"
            return "INFO: Nenhum resultado encontrado na Knowledge Base para esta query."

    except Exception as e:
        logger.error(f"ERRO INESPERADO ao consultar a Knowledge Base: {type(e).__name__} - {e}")
        return f"ERRO INTERNO DA FERRAMENTA: Falha ao consultar a Knowledge Base. Detalhes: {type(e).__name__}"

if BASETOOL_AVAILABLE:
    # Versión usando BaseTool (preferida)
    class KnowledgeBaseQueryTool(BaseTool):
        """
        Ferramenta CrewAI para consultar uma Knowledge Base (KB) implementada
        com Supabase e pgvector. Recebe uma query em linguagem natural,
        gera um embedding para ela, e busca por chunks de texto semanticamente
        similares na KB. Retorna os chunks de texto mais relevantes.
        """
        name: str = "Knowledge Base Query Tool"
        description: str = (
            "Consulta a base de conhecimento interna para encontrar informações relevantes, "
            "casos passados, políticas ou regras específicas. Use para obter contexto adicional "
            "ou respostas para perguntas que exigem conhecimento especializado armazenado."
        )
        args_schema: Type[BaseModel] = KnowledgeBaseQueryToolSchema

        _supabase_client: Optional[SupabaseClient] = None
        _embedding_model: Optional[SentenceTransformer] = None

        # Adicionar variáveis para armazenar as configs que antes eram globais
        _supabase_url: Optional[str] = None
        _supabase_service_key: Optional[str] = None
        _kb_table_name: str = KB_TABLE_NAME_DEFAULT
        _embedding_model_name: str = EMBEDDING_MODEL_NAME_DEFAULT

        def __init__(self, **kwargs):
            """
            Inicializa a ferramenta, o cliente Supabase e o modelo de embedding.
            As variáveis de ambiente são lidas AQUI, no momento da instanciação.
            """
            super().__init__(**kwargs)

            # Ler as variáveis de ambiente no momento da instanciação
            self._supabase_url = os.getenv("SUPABASE_URL")
            self._supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")
            self._kb_table_name = os.getenv("KB_TABLE_NAME", KB_TABLE_NAME_DEFAULT)
            self._embedding_model_name = os.getenv("EMBEDDING_MODEL_NAME", EMBEDDING_MODEL_NAME_DEFAULT)

            if not self._supabase_url or not self._supabase_service_key:
                print(f"ALERTA (KnowledgeBaseQueryTool): Variáveis SUPABASE_URL ({self._supabase_url is not None}) ou SUPABASE_SERVICE_KEY ({self._supabase_service_key is not None}) não configuradas ou faltando. A ferramenta pode não funcionar.")
                self._supabase_client = None
                self._embedding_model = None
                return

            try:
                self._supabase_client = create_client(self._supabase_url, self._supabase_service_key)
                print("INFO: Cliente Supabase inicializado para a KnowledgeBaseQueryTool.")
            except Exception as e:
                print(f"ERRO CRÍTICO (KnowledgeBaseQueryTool): Não foi possível inicializar o cliente Supabase: {e}")
                self._supabase_client = None

            try:
                self._embedding_model = SentenceTransformer(self._embedding_model_name)
                print(f"INFO: Modelo de embedding '{self._embedding_model_name}' carregado para KnowledgeBaseQueryTool.")
            except Exception as e:
                print(f"ERRO CRÍTICO (KnowledgeBaseQueryTool): Não foi possível carregar o modelo de embedding '{self._embedding_model_name}': {e}")
                self._embedding_model = None

        def _run(self, query: str, top_k: int = 3) -> str:
            return _run_kb_query(query, top_k)

else:
    # Versión usando decorador @tool como fallback
    from crewai.tools import tool
    
    @tool("Knowledge Base Query Tool")
    def KnowledgeBaseQueryTool(query: str, top_k: int = 3) -> str:
        """Consulta a base de conhecimento interna para encontrar informações relevantes, casos passados, políticas ou regras específicas. Use para obter contexto adicional ou respostas para perguntas que exigem conhecimento especializado armazenado."""
        return _run_kb_query(query, top_k)

# --- Bloco de Teste Local (Conceitual) ---
if __name__ == '__main__':
    print("INFO: Iniciando teste local da KnowledgeBaseQueryTool...")

    # --- !!! IMPORTANTE: Configure suas variáveis de ambiente ANTES de rodar !!! ---
    # Exemplo (substitua com seus valores reais ou defina no seu ambiente):
    # os.environ['SUPABASE_URL'] = 'https://xxxxxxxx.supabase.co'
    # os.environ['SUPABASE_SERVICE_KEY'] = 'seu_service_role_key'
    # os.environ['KB_TABLE_NAME'] = 'knowledge_base_chunks' # ou o nome da sua tabela
    # os.environ['EMBEDDING_MODEL_NAME'] = 'sentence-transformers/all-MiniLM-L6-v2'

    # kb_tool: Optional[KnowledgeBaseQueryTool] = None
    # try:
    #     kb_tool = KnowledgeBaseQueryTool()
    #     # A verificação de inicialização agora deve ser baseada nos atributos da instância
    #     if not kb_tool._supabase_client or not kb_tool._embedding_model:
    #         print("ERRO: Falha na inicialização da ferramenta KBTool. Verifique os logs de alerta/erro da ferramenta.")
    #         exit(1)
    # except Exception as e:
    #     print(f"ERRO ao instanciar a ferramenta KBTool: {e}")
    #     exit(1)

    # As mensagens de print sobre requisitos ainda são válidas, mas o acesso direto
    # a SUPABASE_URL e KB_TABLE_NAME a partir daqui não reflete o estado da instância.

    queries_de_teste = [
        "Qual a política para validação de Contrato Social emitido há mais de 3 anos?",
        "casos de fraude envolvendo alteração de quadro societário",
        "documentação necessária para procurador de PJ"
    ]

    for q_idx, test_query in enumerate(queries_de_teste):
        print(f"\n--- Testando Query {q_idx + 1}: '{test_query}' ---")
        try:
            # Passando como dicionário para o método run da BaseTool
            resultado_kb = kb_tool.run({"query": test_query, "top_k": 2})
            print("\nResultado da Consulta à KB:")
            print("---------------------------")
            print(resultado_kb)
            print("---------------------------")
        except Exception as e:
            print(f"ERRO CRÍTICO durante o teste da KB: {type(e).__name__} - {e}")

    print("\nINFO: Teste local da KnowledgeBaseQueryTool concluído.") 