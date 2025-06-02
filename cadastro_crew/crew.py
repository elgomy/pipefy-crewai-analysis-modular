# from crewai import Agent, Crew, Process, Task # Agent, Task ya no son directamente usados aquí por la clase @CrewBase
from crewai import Crew, Process, Agent, Task # Mantener Crew y Process para la segunda clase, Agent y Task para la nueva
from crewai.project import CrewBase, agent, crew, task
# from crewai.agents.agent_builder.base_agent import BaseAgent # No es necesario para @agent
# from typing import List # No es necesario para @agent

# Importar agentes e tarefas definidos localmente
from .agents import CadastroAgents
from .tasks import CadastroTasks

# Opcional: para carregar variáveis de ambiente se não estiverem já carregadas
# from dotenv import load_dotenv
# load_dotenv()

# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

# @CrewBase
# class CadastroCrew():
#     """CadastroCrew crew"""

#     agents: List[BaseAgent]
#     tasks: List[Task]

#     # Learn more about YAML configuration files here:
#     # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
#     # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    
#     # If you would like to add tools to your agents, you can learn more about it here:
#     # https://docs.crewai.com/concepts/agents#agent-tools
#     @agent
#     def researcher(self) -> Agent:
#         return Agent(
#             config=self.agents_config['researcher'], # type: ignore[index]
#             verbose=True
#         )

#     @agent
#     def reporting_analyst(self) -> Agent:
#         return Agent(
#             config=self.agents_config['reporting_analyst'], # type: ignore[index]
#             verbose=True
#         )

#     # To learn more about structured task outputs,
#     # task dependencies, and task callbacks, check out the documentation:
#     # https://docs.crewai.com/concepts/tasks#overview-of-a-task
#     @task
#     def research_task(self) -> Task:
#         return Task(
#             config=self.tasks_config['research_task'], # type: ignore[index]
#         )

#     @task
#     def reporting_task(self) -> Task:
#         return Task(
#             config=self.tasks_config['reporting_task'], # type: ignore[index]
#             output_file='report.md'
#         )

#     @crew
#     def crew(self) -> Crew:
#         """Creates the CadastroCrew crew"""
#         # To learn how to add knowledge sources to your crew, check out the documentation:
#         # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

#         return Crew(
#             agents=self.agents, # Automatically created by the @agent decorator
#             tasks=self.tasks, # Automatically created by the @task decorator
#             process=Process.sequential,
#             verbose=True,
#             # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
#         )

@CrewBase
class CadastroCrewCliRunner():
    """
    Crew para ser ejecutada por la CLI de CrewAI.
    Utiliza los agentes y tareas definidos en CadastroAgents y CadastroTasks.
    """
    # inputs: dict = Field(description="Inputs for the crew") # Si necesitas definir inputs explícitos para la CLI

    def __init__(self):
        self._agents_manager = CadastroAgents()
        self._tasks_manager = CadastroTasks()
        # Crear instancias de los agentes para que los métodos @agent los devuelvan
        self.agente_triagem_instance = self._agents_manager.triagem_validador_agente()
        self.agente_extrator_instance = self._agents_manager.extrator_info_agente()
        self.agente_risco_instance = self._agents_manager.analista_risco_agente()

    @agent
    def triagem_validador(self) -> Agent:
        return self.agente_triagem_instance

    @agent
    def extrator_info(self) -> Agent:
        return self.agente_extrator_instance

    @agent
    def analista_risco(self) -> Agent:
        return self.agente_risco_instance

    @task
    def validacao_documental_task(self) -> Task:
        return self._tasks_manager.tarefa_validacao_documental(
            agent=self.triagem_validador() 
        )

    @task
    def extracao_dados_task(self) -> Task:
        return self._tasks_manager.tarefa_extracao_dados(
            agent=self.extrator_info(), 
            context_tasks=[self.validacao_documental_task()] 
        )

    @task
    def analise_risco_task(self) -> Task:
        return self._tasks_manager.tarefa_analise_risco(
            agent=self.analista_risco(), 
            context_tasks=[
                self.validacao_documental_task(),
                self.extracao_dados_task()
            ]
        )

    @crew
    def kickoff_crew(self) -> Crew: # Renombrado el método para evitar colisión con el decorador @crew si se interpreta mal
        """Crea y configura la crew para la CLI."""
        return Crew(
            agents=[
                self.triagem_validador(),
                self.extrator_info(),
                self.analista_risco()
            ],
            tasks=[
                self.validacao_documental_task(),
                self.extracao_dados_task(),
                self.analise_risco_task()
            ],
            process=Process.sequential,
            verbose=True
        )

class CadastroCrew:
    """
    Orquestra o "Crew de Cadastro" para validação documental, extração de dados e análise de risco.
    """
    def __init__(self, inputs=None):
        """
        Inicializa o crew com os inputs necessários.
        O dicionário `inputs` deve conter chaves como:
        - case_id: str
        - documents: list[dict] (ex: [{'type': 'CNPJ', 'location': 'url1'}, ...])
        - checklist_content: str (conteúdo textual do checklist)
        - current_date: str (data atual YYYY-MM-DD)
        - E potencialmente outros campos que as tasks esperam, como dados_pj.cnpj, lista_cpfs_socios
          se já forem conhecidos antes da execução da tarefa de extração.
        """
        self.inputs = inputs if inputs else {}

    def run(self):
        """
        Monta e executa o Crew.
        Retorna o resultado da execução do Crew.
        """
        # Instanciar os gerenciadores de agentes e tarefas
        agents_manager = CadastroAgents()
        tasks_manager = CadastroTasks()

        # Criar os agentes
        agente_triagem = agents_manager.triagem_validador_agente()
        agente_extrator = agents_manager.extrator_info_agente()
        agente_risco = agents_manager.analista_risco_agente()

        # Criar as tarefas
        # A ordem e o contexto são importantes aqui
        # Tarefa 1: Validação Documental
        task_validacao = tasks_manager.tarefa_validacao_documental(agente_triagem)

        # Tarefa 2: Extração de Dados
        # Esta tarefa pode depender do resultado da validação (implicitamente, pois usa os mesmos documentos)
        # ou explicitamente se a validação gerar um output que a extração precise.
        # Por agora, vamos assumir uma dependência sequencial simples.
        task_extracao = tasks_manager.tarefa_extracao_dados(
            agente_extrator,
            context_tasks=[task_validacao] # Resultado da validação pode ser útil
        )

        # Tarefa 3: Análise de Risco e Inconsistências
        # Esta tarefa depende criticamente dos dados extraídos pela task_extracao.
        # Também pode usar o resultado da task_validacao para entender pendências.
        task_analise = tasks_manager.tarefa_analise_risco(
            agente_risco,
            context_tasks=[task_validacao, task_extracao] 
        )

        # Montar o Crew
        crew = Crew(
            agents=[
                agente_triagem,
                agente_extrator,
                agente_risco
            ],
            tasks=[
                task_validacao,
                task_extracao,
                task_analise
            ],
            process=Process.sequential,  # Processo sequencial por padrão
            verbose=True, # MODIFICADO DE 2 A True
            # memory=True, # Descomente se quiser habilitar memória de curto prazo entre tarefas
            # cache=True, # Descomente para habilitar cache de LLM para execuções repetidas
            # max_rpm=100, # Limite de requisições por minuto (se aplicável ao seu LLM)
            # manager_llm=seu_llm_configurado # LLM para o gerente do Crew (se usar processo hierárquico)
        )

        # Executar o Crew com os inputs fornecidos na inicialização da classe CadastroCrew
        # Os inputs serão automaticamente disponibilizados para as tasks que os referenciam.
        print("INFO: Iniciando o kickoff do CadastroCrew...")
        print(f"INFO: Inputs para o kickoff: {self.inputs}")
        
        result = crew.kickoff(inputs=self.inputs)
        return result

# Exemplo de como usar esta clase en main.py:
# from .crew import CadastroCrew
# if __name__ == "__main__":
#     inputs = {
#         'case_id': 'CASO-001',
#         'documents': [
#             {'type': 'CNPJ', 'location': 'url_do_cartao_cnpj.pdf', 'parsing_preset_override': 'detailed'},
#             {'type': 'ContratoSocial', 'location': 'path/to/contrato.pdf'}
#         ],
#         'checklist_content': """
#             Item 1: Validar Cartão CNPJ - Deve estar ativo e emitido nos últimos 30 dias.
#             Item 2: Validar Contrato Social - Deve conter cláusula XYZ.
#             Item 3: ...
#         """,
#         'current_date': '2025-05-17',
#         # Outros inputs que as tasks possam precisar para los placeholders
#         # 'dados_pj.cnpj': 'XX.XXX.XXX/0001-XX', # Exemplo, se já conhecido
#         # 'lista_cpfs_socios': ['111.222.333-44'] # Exemplo, se já conhecido
#     }
#     cadastro_crew_instance = CadastroCrew(inputs=inputs)
#     resultado_final = cadastro_crew_instance.run()
#     print("\n\nRESULTADO FINAL DO CREW:")
#     print(resultado_final)
