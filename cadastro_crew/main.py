#!/usr/bin/env python
import sys
import warnings
from textwrap import dedent
from datetime import datetime
import os
from dotenv import load_dotenv
from pathlib import Path # Adicionado para manipulação de caminhos
import yaml
from supabase import create_client, Client # Added supabase imports

from .crew import CadastroCrew
from .tools import SupabaseDocumentContentTool # Importar a nova ferramenta

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

# Carregar variáveis de ambiente do arquivo .env
# É bom chamar isso o mais cedo possível.
dotenv_path = Path(__file__).resolve().parent.parent.parent / '.env'
print(f"INFO: Caminho construído para .env: {dotenv_path}")
print(f"INFO: Verificando existência de .env em {dotenv_path}: {dotenv_path.exists()}")

# Tentar carregar o .env e verificar o resultado
loaded_env = load_dotenv(dotenv_path=dotenv_path, verbose=True) # verbose=True pode dar mais output
print(f"INFO: Resultado de load_dotenv(verbose=True): {loaded_env}")

# Logs para depuração da carga do .env
# Removido o print anterior "Tentando carregar..." pois agora temos mais detalhes

# Adicionar uma verificação imediata para ver se as variáveis foram carregadas
print(f"DEBUG PÓS-LOAD_DOTENV: SUPABASE_URL é: [{os.getenv('SUPABASE_URL')}]")
print(f"DEBUG PÓS-LOAD_DOTENV: SUPABASE_SERVICE_KEY (esperado) é: [{os.getenv('SUPABASE_SERVICE_KEY')}]")

if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_KEY"):
    print(f"ALERTA PÓS-LOAD_DOTENV: SUPABASE_URL ou SUPABASE_SERVICE_KEY (esperado) não foram efetivamente carregadas no ambiente.")
else:
    print("INFO PÓS-LOAD_DOTENV: SUPABASE_URL e SUPABASE_SERVICE_KEY (esperado) parecem estar no ambiente após load_dotenv.")

# ID do projeto Supabase (deve ser o 'id' alfanumérico, não o 'name')
SUPABASE_PROJECT_ID = os.getenv("SUPABASE_PROJECT_ID", "aguoqgqbdbyipztgrmbd") # Usar o ID correto

# Nome da configuração do checklist na tabela app_configs
CHECKLIST_CONFIG_NAME = "checklist_cadastro_pj"
CLIENT_DOC_CONTRATO_NAME = "4- CONTRATO SOCIAL AD PRODUTOS E SERVIÇOS.pdf"
# Adicione outros nomes de documentos do cliente aqui se necessário
# CLIENT_DOC_CNPJ_NAME = "1- CNPJ.pdf"

# Declaração global para o cliente Supabase, será inicializado em setup_supabase_client()
supabase_client: Client | None = None

def setup_supabase_client() -> Client | None:
    """Inicializa e retorna o cliente Supabase. Retorna None em caso de falha."""
    global supabase_client
    if supabase_client is not None:
        return supabase_client

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        print("Erro Crítico: As variáveis de ambiente SUPABASE_URL e SUPABASE_SERVICE_KEY devem ser definidas no arquivo .env.")
        # Considerar não sair aqui, mas permitir que run() falhe graciosamente ou retorne um erro.
        # exit(1) # Ou raise uma exceção específica
        return None 
    
    try:
        supabase_client = create_client(supabase_url, supabase_key)
        print("INFO: Cliente Supabase inicializado com sucesso em main.py (usando SERVICE_KEY conforme especificado).")
        return supabase_client
    except Exception as e:
        print(f"Erro Crítico: Falha ao inicializar o cliente Supabase em main.py: {e}")
        return None

def get_checklist_content_from_checklist_config(client: Client, config_name: str = "checklist_cadastro_pj") -> str:
    """
    Obtém o conteúdo do checklist da tabela checklist_config no Supabase.
    """
    if not client:
        print("Erro: Cliente Supabase não inicializado para get_checklist_content_from_checklist_config.")
        return ""
    try:
        response = client.table("checklist_config").select("checklist_url").eq("config_name", config_name).single().execute()
        if response.data and response.data.get("checklist_url"):
            checklist_url = response.data["checklist_url"]
            print(f"Checklist URL '{config_name}' obtida de checklist_config: {checklist_url}")
            
            # Aquí podrías descargar y parsear el PDF del checklist
            # Por ahora retornamos un contenido simulado
            checklist_content = """
# CHECKLIST CADASTRO PESSOA JURÍDICA

## 1. DOCUMENTOS CADASTRAIS DA PJ
- [ ] Contrato Social ou Estatuto Social (original ou cópia autenticada)
- [ ] Última alteração contratual (se houver)
- [ ] Cartão CNPJ (emitido nos últimos 90 dias)
- [ ] Inscrição Estadual (se aplicável)
- [ ] Inscrição Municipal (se aplicável)

## 2. DOCUMENTOS FINANCEIROS DA PJ
- [ ] Faturamento dos últimos 12 meses (assinado pelo contador)
- [ ] Balanço Patrimonial (se aplicável)
- [ ] DRE - Demonstração do Resultado do Exercício (se aplicável)

## 3. DOCUMENTOS DOS SÓCIOS/REPRESENTANTES
- [ ] RG e CPF de todos os sócios
- [ ] Comprovante de residência dos sócios (emitido nos últimos 90 dias)
- [ ] Certidão de casamento (se aplicável)

## 4. CRITÉRIOS DE VALIDAÇÃO
- Documentos devem estar legíveis e sem rasuras
- Datas de emissão dentro dos prazos especificados
- Informações consistentes entre documentos
- Assinaturas válidas quando requeridas
"""
            return checklist_content
        else:
            print(f"Erro: Checklist '{config_name}' não encontrado na tabela checklist_config ou URL vazia.")
            return "" # Retorna string vazia para evitar falha total, mas idealmente tratar o erro.
    except Exception as e:
        print(f"Erro ao buscar checklist de checklist_config: {e}")
        return ""

def get_documents_for_case(client: Client, case_id: str) -> list:
    """
    Obtém a lista de documentos e seus tags para um case_id específico da tabela documents.
    """
    if not client:
        print("Erro: Cliente Supabase não inicializado para get_documents_for_case.")
        return []
        
    document_list_for_crew = []
    # Mapeamento de document_tag (BD) para o 'type' esperado pela Crew/Agentes
    tag_to_crew_type_map = {
        "contrato_social": "ContratoSocial",
        "cnpj": "CNPJ",
        "comp_endereco_socio": "ComprovanteEnderecoSocio",
        "qsa": "QuadroSocietario",
        "doc_id_socio": "DocumentoIdentificacaoSocio",
        "certidao_simplificada": "CertidaoSimplificada",
        # Adicione outros mapeamentos conforme necessário
    }

    try:
        response = client.table("documents").select("name, document_tag").eq("case_id", case_id).execute()
        if response.data:
            for doc in response.data:
                doc_name = doc.get("name")
                doc_tag = doc.get("document_tag")
                crew_doc_type = tag_to_crew_type_map.get(doc_tag)

                if doc_name and crew_doc_type: # Só adiciona se tiver nome e um tipo mapeado
                    document_list_for_crew.append({
                        "type": crew_doc_type,
                        "name": doc_name,
                        "case_id": case_id  # O case_id é o mesmo para todos os documentos deste caso
                    })
                elif doc_name and not crew_doc_type:
                    print(f"Aviso: Documento '{doc_name}' com tag '{doc_tag}' não possui mapeamento para tipo da crew. Será ignorado nos inputs.")
            # print(f"Documentos para o case_id '{case_id}' carregados dinamicamente: {document_list_for_crew}")
        else:
            print(f"Nenhum documento encontrado para o case_id '{case_id}' na tabela documents.")
        return document_list_for_crew
    except Exception as e:
        print(f"Erro ao buscar documentos para o case_id '{case_id}': {e}")
        return []

def run():
    """
    Função principal para configurar e executar a CadastroCrew.
    """
    print("INFO: Iniciando a execução da CadastroCrew a partir de main.py...")
    
    # Inicializar o cliente Supabase
    s_client = setup_supabase_client()
    if not s_client:
        print("ERRO FATAL: Não foi possível inicializar o cliente Supabase. Saindo.")
        return

    try:
        # Obter o conteúdo do checklist da tabela app_configs
        parsed_checklist_content = get_checklist_content_from_checklist_config(s_client)
    except Exception as e: # Captura exceções mais genéricas da carga do checklist
        print(f"ERRO FATAL: Não foi possível carregar o checklist. {e}")
        print("Verifique a configuração do Supabase (URL, KEY) e a existência do item na tabela 'checklist_config'.")
        return # Abortar se o checklist não puder ser carregado

    # Inputs para a crew
    case_id = os.getenv('CASE_ID', 'CASO-CLIENTE-REAL-001')

    # Obter dinamicamente a lista de documentos para o case_id
    dynamic_documents_list = get_documents_for_case(s_client, case_id)

    if not dynamic_documents_list:
        print(f"Nenhum documento configurado para ser processado para o case_id '{case_id}'. Verifique a tabela 'documents' e os 'document_tag'.")
        # Poderia abortar aqui ou continuar dependendo da lógica desejada
        # return 
    
    # Inputs para a crew
    inputs = {
        'case_id': case_id,
        'documents': dynamic_documents_list, # Lista de documentos carregada dinamicamente
        'checklist': parsed_checklist_content, 
        'current_date': datetime.now().strftime('%Y-%m-%d'),
        'dados_pj.cnpj': os.getenv('DADOS_PJ_CNPJ_FALLBACK', ''), # Este CNPJ é para a tarefa_geracao_relatorio
        'lista_cpfs_socios': [], 
        'cpf_socio_principal': os.getenv('CPF_SOCIO_PRINCIPAL_FALLBACK', '') 
    }

    print(f"DEBUG: Inputs preparados para a CadastroCrew: {inputs}")

    cadastro_crew = CadastroCrew(inputs=inputs)
    print("INFO: Iniciando a execução do método run() do CadastroCrew...")
    try:
        resultado = cadastro_crew.run()
        print("\n---\nRESULTADO FINAL DA EXECUÇÃO DO CREW:\n")
        print(resultado)
        print("---")

        # Salvar o resultado em um arquivo Markdown
        try:
            # Determinar o diretório raiz do projeto (assumindo que main.py está em src/cadastro_crew)
            project_root = Path(__file__).resolve().parent.parent.parent 
            reports_dir = project_root / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True) # Cria o diretório se não existir

            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            file_name = f"relatorio_crew_{timestamp}.md"
            file_path = reports_dir / file_name

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# Relatório da Execução da Crew - {timestamp}\\n\\n")
                f.write("## Inputs Fornecidos:\\n\\n")
                # Para não expor chaves de API ou conteúdo muito longo do checklist nos inputs do relatório
                safe_inputs_to_log = {k: v for k, v in inputs.items() if k != 'checklist'}
                safe_inputs_to_log['checklist_length'] = len(inputs.get('checklist', ''))
                
                import json
                f.write(f"```json\\n{json.dumps(safe_inputs_to_log, indent=2, ensure_ascii=False)}\\n```\\n\\n")
                f.write("## Resultado da Crew:\\n\\n")
                if isinstance(resultado, str):
                    f.write(resultado)
                else:
                    # Se o resultado não for uma string (ex: objeto complexo), converter para string
                    f.write(str(resultado))
            
            print(f"INFO: Resultado da crew salvo em: {file_path}")

        except Exception as e_save:
            print(f"AVISO: Falha ao salvar o resultado da crew em arquivo: {e_save}")

    except Exception as e:
        print(f"ERRO: Uma exceção ocorreu durante a execução da crew: {e}")
        import traceback
        traceback.print_exc()

def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        "topic": "AI LLMs",
        'current_year': str(datetime.now().year)
    }
    try:
        CadastroCrew().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        CadastroCrew().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        "topic": "AI LLMs",
        "current_year": str(datetime.now().year)
    }
    
    try:
        CadastroCrew().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")

if __name__ == "__main__":
    # Este bloco permite executar o main.py diretamente com `python -m cadastro_crew.main`
    # ou `python src/cadastro_crew/main.py` (dependendo de como PYTHONPATH está configurado)
    run()
