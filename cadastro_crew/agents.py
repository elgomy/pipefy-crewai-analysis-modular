import yaml
from pathlib import Path
from crewai import Agent
from crewai_tools import SerperDevTool

# Importar ferramentas customizadas con fallbacks robustos
try:
    from .tools.llama_cloud_parsing_tool import LlamaParseDirectTool
    LLAMA_PARSE_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: LlamaParseDirectTool no disponible: {e}")
    LlamaParseDirectTool = None
    LLAMA_PARSE_AVAILABLE = False

try:
    from .tools import KnowledgeBaseQueryTool
    KB_TOOL_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: KnowledgeBaseQueryTool no disponible: {e}")
    KnowledgeBaseQueryTool = None
    KB_TOOL_AVAILABLE = False

# Intentar importar la herramienta original, si falla usar la simplificada
try:
    from .tools import SupabaseDocumentContentTool
    SUPABASE_TOOL_AVAILABLE = True
    USING_SIMPLE_TOOL = False
    print("INFO: Usando SupabaseDocumentContentTool original")
except ImportError as e:
    print(f"WARNING: SupabaseDocumentContentTool original no disponible: {e}")
    try:
        from .tools.simple_supabase_tool import get_supabase_document_info
        SupabaseDocumentContentTool = get_supabase_document_info
        SUPABASE_TOOL_AVAILABLE = True
        USING_SIMPLE_TOOL = True
        print("INFO: Usando herramienta Supabase simplificada")
    except ImportError as e2:
        print(f"ERROR: Ninguna herramienta Supabase disponible: {e2}")
        SupabaseDocumentContentTool = None
        SUPABASE_TOOL_AVAILABLE = False
        USING_SIMPLE_TOOL = False

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
        
        # SerperDevTool siempre disponível
        self.serper_tool = SerperDevTool()
        
        # Knowledge Base Tool
        if KB_TOOL_AVAILABLE:
            try:
                self.kb_tool = KnowledgeBaseQueryTool()
                self.kb_available = True
                print("INFO (CadastroAgents): KnowledgeBaseQueryTool disponible.")
            except Exception as e:
                print(f"WARNING (CadastroAgents): Error al inicializar KnowledgeBaseQueryTool: {e}")
                self.kb_tool = None
                self.kb_available = False
        else:
            self.kb_tool = None
            self.kb_available = False
        
        # Supabase Tool
        if SUPABASE_TOOL_AVAILABLE:
            try:
                if USING_SIMPLE_TOOL:
                    # La herramienta simplificada ya es una función decorada
                    self.supabase_doc_tool = SupabaseDocumentContentTool
                    print("INFO (CadastroAgents): Herramienta Supabase simplificada disponible.")
                else:
                    # Herramienta original que necesita instanciación
                    self.supabase_doc_tool = SupabaseDocumentContentTool()
                    print("INFO (CadastroAgents): SupabaseDocumentContentTool original disponible.")
                self.supabase_available = True
            except Exception as e:
                print(f"WARNING (CadastroAgents): Error al inicializar herramienta Supabase: {e}")
                self.supabase_doc_tool = None
                self.supabase_available = False
        else:
            self.supabase_doc_tool = None
            self.supabase_available = False
        
        # LlamaParse Tool
        if LLAMA_PARSE_AVAILABLE:
            try:
                self.llama_parse_tool = LlamaParseDirectTool()
                self.llama_available = True
                print("INFO (CadastroAgents): LlamaCloud disponible.")
            except Exception as e:
                print(f"WARNING (CadastroAgents): LlamaCloud no disponible: {e}")
                self.llama_parse_tool = None
                self.llama_available = False
        else:
            self.llama_parse_tool = None
            self.llama_available = False
            
        print("INFO (CadastroAgents): Ferramentas inicializadas.")

    def triagem_validador_agente(self) -> Agent:
        config = agents_config['triagem_agente']
        tools = []
        
        if self.supabase_available:
            tools.append(self.supabase_doc_tool)
        if self.kb_available:
            tools.append(self.kb_tool)
        if self.llama_available:
            tools.append(self.llama_parse_tool)
            
        return Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            verbose=config.get('verbose', True),
            allow_delegation=config.get('allow_delegation', False),
            tools=tools,
        )

    def extrator_info_agente(self) -> Agent:
        config = agents_config['extrator_agente']
        tools = []
        
        if self.supabase_available:
            tools.append(self.supabase_doc_tool)
        if self.llama_available:
            tools.append(self.llama_parse_tool)
            
        return Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            verbose=config.get('verbose', True),
            allow_delegation=config.get('allow_delegation', False),
            tools=tools,
        )

    def analista_risco_agente(self) -> Agent:
        config = agents_config['risco_agente']
        tools = []
        
        if self.supabase_available:
            tools.append(self.supabase_doc_tool)
        tools.append(self.serper_tool)  # SerperDevTool siempre disponible
        if self.kb_available:
            tools.append(self.kb_tool)
        if self.llama_available:
            tools.append(self.llama_parse_tool)
            
        return Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            verbose=config.get('verbose', True),
            allow_delegation=config.get('allow_delegation', False),
            tools=tools,
        )

# Exemplo de como você poderia usar esta classe em seu crew.py:
# from .agents import CadastroAgents
# agents_manager = CadastroAgents()
# agente_triagem = agents_manager.triagem_validador_agente()
# agente_extrator = agents_manager.extrator_info_agente()
# agente_risco = agents_manager.analista_risco_agente() 