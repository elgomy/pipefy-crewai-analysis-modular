import yaml
from pathlib import Path
from crewai import Task

# Carregar configurações das tarefas do arquivo YAML
tasks_config_path = Path(__file__).parent / 'config/tasks.yaml'
with open(tasks_config_path, 'r', encoding='utf-8') as file:
    tasks_config = yaml.safe_load(file)

class CadastroTasks:
    """
    Classe para criar e configurar as Tarefas do "Crew de Cadastro".
    As definições (description, expected_output) são carregadas do tasks.yaml.
    Os agentes são atribuídos aqui ao criar a Task.
    Os placeholders nas descriptions serão preenchidos via o dicionário `inputs` 
    passado para `Crew.kickoff()` e gerenciados pelo contexto da CrewAI.
    """

    def tarefa_validacao_documental(self, agente_triagem, context_tasks=None) -> Task:
        config = tasks_config['tarefa_validacao_documental']
        # Os placeholders como {case_id}, {documents}, {checklist}, {current_date}
        # serão interpolados por CrewAI a partir do input inicial do kickoff ou do contexto.
        return Task(
            description=config['description'],
            expected_output=config['expected_output'],
            agent=agente_triagem,
            context=context_tasks if context_tasks else []
            # async_execution=False # Defina como True se a tarefa puder rodar em paralelo
            # output_file=config.get('output_file') # Se definido no YAML
        )

    def tarefa_extracao_dados(self, agente_extrator, context_tasks=None) -> Task:
        config = tasks_config['tarefa_extracao_dados']
        # Placeholders: {case_id}, {documents}
        return Task(
            description=config['description'],
            expected_output=config['expected_output'],
            agent=agente_extrator,
            context=context_tasks if context_tasks else []
            # async_execution=False
            # output_file=config.get('output_file')
        )

    def tarefa_analise_risco(self, agente_risco, context_tasks=None) -> Task:
        config = tasks_config['tarefa_analise_risco_inconsistencias']
        # Placeholders: {case_id}, {dados_pj.cnpj}, {lista_cpfs_socios}
        # Estes últimos ({dados_pj.cnpj}, {lista_cpfs_socios}) provavelmente virão do contexto 
        # da tarefa de extração, ou precisam ser passados no input inicial se já conhecidos.
        return Task(
            description=config['description'],
            expected_output=config['expected_output'],
            agent=agente_risco,
            context=context_tasks if context_tasks else []
            # async_execution=False
            # output_file=config.get('output_file', 'report_analise_risco.md') # Exemplo de output file
        )

# Exemplo de como você poderia usar esta classe em seu crew.py:
# from .tasks import CadastroTasks
# from .agents import CadastroAgents

# agents_manager = CadastroAgents()
# agente_triagem = agents_manager.triagem_validador_agente()
# agente_extrator = agents_manager.extrator_info_agente()
# agente_risco = agents_manager.analista_risco_agente()

# tasks_manager = CadastroTasks()
# task_validacao = tasks_manager.tarefa_validacao_documental(agente_triagem)
# task_extracao = tasks_manager.tarefa_extracao_dados(agente_extrator, context_tasks=[task_validacao])
# task_analise = tasks_manager.tarefa_analise_risco(agente_risco, context_tasks=[task_extracao]) # Depende do resultado da extração 