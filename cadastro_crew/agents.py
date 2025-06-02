import yaml
from pathlib import Path
from crewai import Agent
from crewai_tools import SerperDevTool

# Importar ferramentas customizadas
from .tools.llama_cloud_parsing_tool import LlamaParseDirectTool # Importar a ferramenta de parseo
from .tools import KnowledgeBaseQueryTool
from .tools import SupabaseDocumentContentTool # Nova ferramenta

# Carregar configurações dos agentes do arquivo YAML
agents_config_path = Path(__file__).parent / 'config/agents.yaml'
with open(agents_config_path, 'r', encoding='utf-8') as file:
    agents_config = yaml.safe_load(file)

# NÃO instanciar ferramentas aqui a nível de módulo
# serper_tool = SerperDevTool()
# kb_tool = KnowledgeBaseQueryTool()
# supabase_doc_tool = SupabaseDocumentContentTool()

class CadastroAgents:
    """
    Classe para criar e configurar os agentes do "Crew de Cadastro".
    As definições base (role, goal, backstory) são carregadas do agents.yaml.
    As ferramentas são atribuídas aqui.
    """
    def __init__(self):
        # Instanciar ferramentas aqui, dentro do __init__
        # Isto garante que são criadas APÓS load_dotenv() em main.py ter sido chamado,
        # assumindo que CadastroAgents() é chamado depois disso.
        print("INFO (CadastroAgents): Inicializando ferramentas...")
        self.serper_tool = SerperDevTool()
        self.kb_tool = KnowledgeBaseQueryTool()
        self.supabase_doc_tool = SupabaseDocumentContentTool()
        
        # Hacer LlamaCloud opcional
        try:
            self.llama_parse_tool = LlamaParseDirectTool()
            self.llama_available = True
            print("INFO (CadastroAgents): LlamaCloud disponible.")
        except ValueError as e:
            print(f"WARNING (CadastroAgents): LlamaCloud no disponible: {e}")
            self.llama_parse_tool = None
            self.llama_available = False
            
        print("INFO (CadastroAgents): Ferramentas inicializadas.")

    def triagem_validador_agente(self) -> Agent:
        config = agents_config['triagem_agente']
        tools = [self.supabase_doc_tool, self.kb_tool]
        if self.llama_available:
            tools.append(self.llama_parse_tool)
            
        return Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            verbose=config.get('verbose', True),
            allow_delegation=config.get('allow_delegation', False),
            tools=tools,
            # llm=seu_llm_configurado # Opcional: se quiser um LLM específico para este agente
        )

    def extrator_info_agente(self) -> Agent:
        config = agents_config['extrator_agente']
        tools = [self.supabase_doc_tool]
        if self.llama_available:
            tools.append(self.llama_parse_tool)
            
        return Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            verbose=config.get('verbose', True),
            allow_delegation=config.get('allow_delegation', False),
            tools=tools,
            # llm=seu_llm_configurado
        )

    def analista_risco_agente(self) -> Agent:
        config = agents_config['risco_agente']
        tools = [self.supabase_doc_tool, self.serper_tool, self.kb_tool]
        if self.llama_available:
            tools.append(self.llama_parse_tool)
            
        return Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            verbose=config.get('verbose', True),
            allow_delegation=config.get('allow_delegation', False),
            tools=tools,
            # llm=seu_llm_configurado
        )

# Exemplo de como você poderia usar esta classe em seu crew.py:
# from .agents import CadastroAgents
# agents_manager = CadastroAgents()
# agente_triagem = agents_manager.triagem_validador_agente()
# agente_extrator = agents_manager.extrator_info_agente()
# agente_risco = agents_manager.analista_risco_agente() 