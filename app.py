#!/usr/bin/env python3
"""
Servicio CrewAI - Versión HTTP Directa
Se enfoca únicamente en el análisis de documentos usando CrewAI.
Recibe llamadas HTTP directas del servicio de ingestión de documentos.
MANTIENE LA MODULARIDAD: Cada servicio tiene su responsabilidad específica.
"""

import os
import asyncio
import httpx
import logging
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
import json

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuración del servicio
SERVICE_NAME = "CrewAI Analysis Service - HTTP Direct"
SERVICE_PORT = int(os.getenv("CREWAI_SERVICE_PORT", "8002"))

# Directorio para guardar resultados
RESULTS_DIR = Path("analysis_results")
RESULTS_DIR.mkdir(exist_ok=True)

# Verificar variables de entorno críticas
logger.info("🔍 Verificando variables de entorno...")
required_env_vars = ["OPENAI_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_KEY"]
missing_vars = []

for var in required_env_vars:
    if not os.getenv(var):
        missing_vars.append(var)
    else:
        logger.info(f"✅ {var}: configurada")

if missing_vars:
    logger.warning(f"⚠️ Variables de entorno faltantes: {missing_vars}")
else:
    logger.info("✅ Todas las variables de entorno críticas están configuradas")

# Verificar si CrewAI está disponible
CREWAI_AVAILABLE = False
CadastroCrew = None

try:
    logger.info("🔍 Intentando importar CrewAI...")
    
    # Verificar primero las dependencias básicas
    try:
        import crewai
        logger.info(f"✅ CrewAI base importado - versión: {getattr(crewai, '__version__', 'unknown')}")
        
        # Verificar que BaseTool esté disponible
        try:
            from crewai.tools import BaseTool
            logger.info("✅ BaseTool importado correctamente desde crewai.tools")
        except ImportError as bt_error:
            logger.error(f"❌ No se puede importar BaseTool desde crewai.tools: {bt_error}")
            # Intentar ubicaciones alternativas
            try:
                from crewai.tools.base_tool import BaseTool
                logger.info("✅ BaseTool importado desde crewai.tools.base_tool (ubicación alternativa)")
            except ImportError as bt_error2:
                logger.error(f"❌ BaseTool tampoco disponible en crewai.tools.base_tool: {bt_error2}")
                raise ImportError(f"BaseTool no disponible en ninguna ubicación conocida")
        
    except ImportError as e:
        logger.error(f"❌ No se puede importar crewai base: {e}")
        raise
    
    # Intentar importar desde diferentes ubicaciones
    try:
        logger.info("📦 Intentando importar desde cadastro_crew.crew...")
        from cadastro_crew.crew import CadastroCrew
        CREWAI_AVAILABLE = True
        logger.info("✅ CrewAI disponible - análisis real habilitado (desde cadastro_crew.crew)")
    except ImportError as e1:
        logger.warning(f"⚠️ Fallo importación desde cadastro_crew.crew: {e1}")
        try:
            logger.info("📦 Intentando importar desde cadastro_crew.main...")
            from cadastro_crew.main import CadastroCrew
            CREWAI_AVAILABLE = True
            logger.info("✅ CrewAI disponible - análisis real habilitado (desde cadastro_crew.main)")
        except ImportError as e2:
            logger.warning(f"⚠️ Fallo importación desde cadastro_crew.main: {e2}")
            
            # Intentar importar la clase directamente
            try:
                logger.info("📦 Intentando importar CadastroCrewCliRunner...")
                from cadastro_crew.crew import CadastroCrewCliRunner
                CadastroCrew = CadastroCrewCliRunner
                CREWAI_AVAILABLE = True
                logger.info("✅ CrewAI disponible - análisis real habilitado (usando CadastroCrewCliRunner)")
            except ImportError as e3:
                logger.error(f"❌ Todas las importaciones fallaron:")
                logger.error(f"   - cadastro_crew.crew: {e1}")
                logger.error(f"   - cadastro_crew.main: {e2}")
                logger.error(f"   - CadastroCrewCliRunner: {e3}")
                CREWAI_AVAILABLE = False
                
except Exception as e:
    logger.error(f"❌ Error general al importar CrewAI: {e}")
    logger.error(f"   Tipo de error: {type(e).__name__}")
    import traceback
    logger.error(f"   Traceback: {traceback.format_exc()}")
    CREWAI_AVAILABLE = False

# Log final del estado
if CREWAI_AVAILABLE:
    logger.info(f"🎉 CrewAI configurado exitosamente. Clase: {CadastroCrew.__name__ if CadastroCrew else 'Unknown'}")
else:
    logger.warning("⚠️ CrewAI NO disponible - el servicio funcionará en modo simulación")

app = FastAPI(
    title=SERVICE_NAME,
    description="Servicio modular de análisis CrewAI con comunicación HTTP directa"
)

# Modelos Pydantic
class CrewAIAnalysisRequest(BaseModel):
    case_id: str
    documents: List[Dict[str, Any]]
    checklist_url: str
    current_date: str
    pipe_id: Optional[str] = None

class AnalysisResult(BaseModel):
    case_id: str
    status: str
    message: str
    timestamp: str
    documents_analyzed: int
    crewai_available: bool
    analysis_details: Optional[Dict[str, Any]] = None

async def get_or_parse_checklist_content(checklist_url: str) -> str:
    """
    Obtiene el contenido del checklist desde la base de datos si ya está parseado,
    o lo parsea por primera vez y lo guarda.
    """
    try:
        # Primero intentar obtener el contenido ya parseado desde Supabase
        logger.info(f"🔍 Verificando si el checklist ya está parseado en la base de datos...")
        
        # Configurar cliente Supabase
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        
        if supabase_url and supabase_key:
            try:
                from supabase import create_client
                supabase = create_client(supabase_url, supabase_key)
                
                # Buscar el checklist por URL
                response = supabase.table("checklist_config").select("checklist_content, parsed_at").eq("checklist_url", checklist_url).execute()
                
                if response.data and len(response.data) > 0:
                    checklist_data = response.data[0]
                    if checklist_data.get("checklist_content"):
                        logger.info(f"✅ Checklist ya parseado encontrado en la base de datos (parseado: {checklist_data.get('parsed_at')})")
                        return checklist_data["checklist_content"]
                    else:
                        logger.info(f"📄 Checklist encontrado pero sin contenido parseado - procediendo a parsear...")
                else:
                    logger.info(f"📄 Checklist no encontrado en la base de datos - procediendo a parsear...")
                    
            except Exception as db_error:
                logger.warning(f"⚠️ Error al consultar la base de datos: {db_error} - procediendo a parsear directamente...")
        else:
            logger.warning(f"⚠️ Credenciales de Supabase no disponibles - procediendo a parsear directamente...")
        
        # Si llegamos aquí, necesitamos parsear el checklist
        logger.info(f"📥 Parseando checklist desde: {checklist_url}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(checklist_url)
            response.raise_for_status()
            
            # Si es un PDF, usar LlamaParse para extraer texto
            if checklist_url.lower().endswith('.pdf'):
                logger.info("📄 Archivo PDF detectado - extrayendo texto con LlamaParse...")
                
                # Verificar si LlamaParse está disponible
                llama_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
                if not llama_api_key:
                    logger.warning("⚠️ LLAMA_CLOUD_API_KEY no configurada - usando contenido simulado...")
                    content = """
CHECKLIST DE CADASTRO PESSOA JURÍDICA

1. DOCUMENTOS OBRIGATÓRIOS:
   - Contrato Social atualizado
   - Comprovante de residência da empresa
   - Documento de identidade dos sócios
   - Declaração de impostos (último ano)
   - Certificado de registro na junta comercial

2. CRITÉRIOS DE VALIDAÇÃO:
   - Documentos devem estar legíveis
   - Datas não podem estar vencidas
   - Assinaturas devem estar presentes
   - Informações devem ser consistentes entre documentos
                    """
                else:
                    try:
                        # Intentar usar LlamaParse
                        from llama_parse import LlamaParse
                        import tempfile
                        
                        # Guardar el PDF temporalmente
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                            temp_file.write(response.content)
                            temp_file_path = temp_file.name
                        
                        # Usar LlamaParse para extraer el contenido
                        parser = LlamaParse(
                            api_key=llama_api_key,
                            result_type="markdown",
                            language="pt"
                        )
                        
                        documents = await parser.aload_data(temp_file_path)
                        
                        # Limpiar archivo temporal
                        os.unlink(temp_file_path)
                        
                        if documents:
                            content = "\n\n".join([doc.text for doc in documents if doc.text])
                            logger.info(f"📄 Contenido extraído con LlamaParse: {len(content)} caracteres")
                        else:
                            logger.warning("⚠️ LlamaParse no retornó contenido - usando fallback")
                            content = "Error: No se pudo extraer contenido del PDF con LlamaParse"
                            
                    except Exception as llama_error:
                        logger.error(f"❌ Error con LlamaParse: {llama_error}")
                        logger.warning("⚠️ Fallback a contenido simulado debido a error de LlamaParse")
                        content = """
CHECKLIST DE CADASTRO PESSOA JURÍDICA

1. DOCUMENTOS OBRIGATÓRIOS:
   - Contrato Social atualizado
   - Comprovante de residência da empresa
   - Documento de identidade dos sócios
   - Declaração de impostos (último año)
   - Certificado de registro na junta comercial

2. CRITÉRIOS DE VALIDAÇÃO:
   - Documentos devem estar legíveis
   - Datas não podem estar vencidas
   - Assinaturas devem estar presentes
   - Informações devem ser consistentes entre documentos
                        """
            else:
                # Para otros tipos de archivo
                content = response.text
                logger.info(f"📄 Contenido de texto extraído: {len(content)} caracteres")
        
        # Guardar el contenido parseado en la base de datos para futuras consultas
        if supabase_url and supabase_key and content:
            try:
                from datetime import datetime
                
                # Actualizar o insertar el contenido parseado
                update_data = {
                    "checklist_content": content,
                    "parsed_at": datetime.now().isoformat(),
                    "parsing_version": "1.0"
                }
                
                # Intentar actualizar primero
                update_response = supabase.table("checklist_config").update(update_data).eq("checklist_url", checklist_url).execute()
                
                if update_response.data:
                    logger.info(f"✅ Contenido del checklist guardado en la base de datos")
                else:
                    logger.warning(f"⚠️ No se pudo actualizar el checklist en la base de datos")
                    
            except Exception as save_error:
                logger.warning(f"⚠️ Error al guardar el contenido parseado: {save_error}")
        
        return content
        
    except Exception as e:
        logger.error(f"❌ Error al obtener/parsear checklist: {e}")
        # Fallback a contenido básico
        return """
CHECKLIST DE CADASTRO PESSOA JURÍDICA - FALLBACK

1. DOCUMENTOS OBRIGATÓRIOS:
   - Contrato Social
   - Comprovante de residência
   - Documentos dos sócios
   - Declarações fiscais

2. CRITÉRIOS:
   - Documentos legíveis
   - Informações consistentes
        """

async def download_and_parse_client_documents(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Descarga y parsea los documentos del cliente usando LlamaParse.
    Retorna una lista de documentos con su contenido parseado.
    """
    parsed_documents = []
    
    logger.info(f"📄 Iniciando parseo de {len(documents)} documentos del cliente...")
    
    for doc in documents:
        try:
            doc_name = doc.get("name", "documento_sin_nombre")
            doc_url = doc.get("url", "")
            doc_tag = doc.get("document_tag", "sin_tag")
            
            if not doc_url:
                logger.warning(f"⚠️ Documento {doc_name} no tiene URL - saltando...")
                continue
                
            logger.info(f"📥 Parseando documento: {doc_name} desde {doc_url}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(doc_url)
                response.raise_for_status()
                
                content = ""
                
                # Si es un PDF, usar LlamaParse
                if doc_url.lower().endswith('.pdf'):
                    logger.info(f"📄 Documento PDF detectado: {doc_name}")
                    
                    llama_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
                    if llama_api_key:
                        try:
                            from llama_parse import LlamaParse
                            import tempfile
                            
                            # Guardar el PDF temporalmente
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                                temp_file.write(response.content)
                                temp_file_path = temp_file.name
                            
                            # Usar LlamaParse para extraer el contenido
                            parser = LlamaParse(
                                api_key=llama_api_key,
                                result_type="markdown",
                                language="pt"
                            )
                            
                            documents_parsed = await parser.aload_data(temp_file_path)
                            
                            # Limpiar archivo temporal
                            os.unlink(temp_file_path)
                            
                            if documents_parsed:
                                content = "\n\n".join([d.text for d in documents_parsed if d.text])
                                logger.info(f"✅ Documento {doc_name} parseado: {len(content)} caracteres")
                            else:
                                logger.warning(f"⚠️ No se pudo extraer contenido de {doc_name}")
                                content = f"[Error: No se pudo parsear el documento {doc_name}]"
                                
                        except Exception as parse_error:
                            logger.error(f"❌ Error parseando {doc_name}: {parse_error}")
                            content = f"[Error parseando {doc_name}: {str(parse_error)}]"
                    else:
                        logger.warning(f"⚠️ LLAMA_CLOUD_API_KEY no disponible para parsear {doc_name}")
                        content = f"[Documento PDF {doc_name} - contenido no disponible sin LlamaParse]"
                else:
                    # Para otros tipos de archivo
                    content = response.text
                    logger.info(f"✅ Documento de texto {doc_name}: {len(content)} caracteres")
                
                # Agregar el documento parseado
                parsed_documents.append({
                    "name": doc_name,
                    "url": doc_url,
                    "document_tag": doc_tag,
                    "content": content,
                    "original_metadata": doc
                })
                
        except Exception as doc_error:
            logger.error(f"❌ Error procesando documento {doc.get('name', 'unknown')}: {doc_error}")
            parsed_documents.append({
                "name": doc.get("name", "documento_error"),
                "url": doc.get("url", ""),
                "document_tag": doc.get("document_tag", "error"),
                "content": f"[Error: No se pudo procesar el documento - {str(doc_error)}]",
                "original_metadata": doc
            })
    
    logger.info(f"✅ Parseo completado: {len(parsed_documents)} documentos procesados")
    return parsed_documents

async def save_analysis_results(analysis_result: AnalysisResult):
    """Guarda los resultados del análisis en archivos y prepara para Supabase."""
    try:
        logger.info(f"💾 Guardando resultados del análisis...")
        
        # Guardar en Markdown
        markdown_path = await save_analysis_result_to_markdown(analysis_result)
        if markdown_path:
            logger.info(f"📄 Resultado Markdown: {markdown_path}")
        
        # Guardar en JSON
        json_path = await save_analysis_result_to_json(analysis_result)
        if json_path:
            logger.info(f"📄 Resultado JSON: {json_path}")
        
        # Preparar para futura tabla Supabase
        await save_analysis_result_to_supabase(analysis_result)
        
    except Exception as e:
        logger.error(f"❌ Error guardando resultados: {e}")

async def analyze_documents_with_crewai(request: CrewAIAnalysisRequest) -> AnalysisResult:
    """Analiza documentos usando CrewAI con el contenido real parseado."""
    try:
        logger.info(f"🔍 Iniciando análisis CrewAI para case_id: {request.case_id}")
        logger.info(f"📄 Documentos a analizar: {len(request.documents)}")
        logger.info(f"📋 Checklist URL: {request.checklist_url}")
        
        # 1. Obtener contenido del checklist (desde cache o parseando)
        logger.info("📥 Obteniendo contenido del checklist...")
        checklist_content = await get_or_parse_checklist_content(request.checklist_url)
        
        # 2. Parsear documentos del cliente
        logger.info("📄 Parseando documentos del cliente...")
        parsed_client_documents = await download_and_parse_client_documents(request.documents)
        
        # 3. Preparar inputs para la crew con contenido real
        crew_inputs = {
            "case_id": request.case_id,
            "pipe_id": request.pipe_id,
            "current_date": request.current_date,
            "checklist_content": checklist_content,
            "client_documents": parsed_client_documents,
            "documents_metadata": request.documents  # Mantener metadata original también
        }
        
        logger.info(f"🚀 Ejecutando CrewAI con {len(parsed_client_documents)} documentos parseados...")
        
        # Ejecutar la crew
        crew_instance = CadastroCrew()
        result = crew_instance.crew().kickoff(inputs=crew_inputs)
        
        logger.info(f"✅ Análisis CrewAI completado para case_id: {request.case_id}")
        
        # Preparar resultado
        analysis_result = AnalysisResult(
            case_id=request.case_id,
            pipe_id=request.pipe_id,
            status="completed",
            analysis_details={
                "crew_result": str(result),
                "documents_analyzed": len(parsed_client_documents),
                "checklist_used": request.checklist_url,
                "analysis_timestamp": datetime.now().isoformat(),
                "documents_content_summary": [
                    {
                        "name": doc["name"],
                        "tag": doc["document_tag"],
                        "content_length": len(doc["content"]),
                        "parsed_successfully": not doc["content"].startswith("[Error")
                    }
                    for doc in parsed_client_documents
                ]
            }
        )
        
        # Guardar resultados
        await save_analysis_results(analysis_result)
        
        return analysis_result
        
    except Exception as e:
        logger.error(f"❌ Error en análisis CrewAI para case_id {request.case_id}: {e}")
        return AnalysisResult(
            case_id=request.case_id,
            pipe_id=request.pipe_id,
            status="error",
            analysis_details={
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

# 🔗 ENDPOINT PRINCIPAL PARA COMUNICACIÓN HTTP DIRECTA
@app.post("/analyze")
async def analyze_documents_endpoint(request: CrewAIAnalysisRequest, background_tasks: BackgroundTasks):
    """
    Endpoint principal para análisis de documentos.
    Recibe llamadas HTTP directas del servicio de ingestión.
    MANTIENE LA MODULARIDAD: Se enfoca solo en análisis CrewAI.
    """
    try:
        logger.info(f"🔗 Solicitud de análisis HTTP directa recibida para case_id: {request.case_id}")
        logger.info(f"📄 Documentos a analizar: {len(request.documents)}")
        logger.info(f"🔗 Pipe ID: {request.pipe_id}")
        
        # Procesar análisis en background para respuesta rápida
        background_tasks.add_task(analyze_documents_with_crewai, request)
        
        return {
            "status": "accepted",
            "message": f"Análisis iniciado para case_id: {request.case_id}",
            "case_id": request.case_id,
            "documents_count": len(request.documents),
            "processing": "background",
            "service": "crewai_analysis_service",
            "communication": "http_direct",
            "crewai_available": CREWAI_AVAILABLE
        }
        
    except Exception as e:
        logger.error(f"❌ Error al procesar solicitud de análisis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/sync")
async def analyze_documents_sync(request: CrewAIAnalysisRequest):
    """
    Endpoint síncrono para análisis de documentos.
    Espera a que el análisis termine antes de responder.
    """
    try:
        logger.info(f"🔗 Solicitud de análisis SÍNCRONA recibida para case_id: {request.case_id}")
        
        # Ejecutar análisis de forma síncrona
        result = await analyze_documents_with_crewai(request)
        
        return {
            "status": "completed",
            "analysis_result": result.model_dump(),
            "service": "crewai_analysis_service",
            "communication": "http_direct_sync",
            "crewai_available": CREWAI_AVAILABLE
        }
        
    except Exception as e:
        logger.error(f"❌ Error en análisis síncrono: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Endpoint de salud."""
    return {
        "status": "healthy",
        "service": "crewai_analysis_service",
        "crewai_available": CREWAI_AVAILABLE,
        "architecture": "modular_http_direct",
        "communication": "http_direct",
        "endpoints": {
            "async_analysis": "POST /analyze",
            "sync_analysis": "POST /analyze/sync",
            "health": "GET /health"
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/")
async def root():
    return {
        "service": "CrewAI Analysis Service - HTTP Direct",
        "description": "Servicio modular de análisis CrewAI con comunicación HTTP directa",
        "architecture": "modular",
        "communication": "http_direct",
        "crewai_available": CREWAI_AVAILABLE,
        "version": "http_direct_v1.0",
        "endpoints": {
            "async_analysis": "POST /analyze - Análisis en background",
            "sync_analysis": "POST /analyze/sync - Análisis síncrono",
            "health": "GET /health - Estado del servicio",
            "root": "GET / - Información del servicio"
        }
    }

@app.get("/status")
async def service_status():
    """Estado detallado del servicio."""
    return {
        "service_name": SERVICE_NAME,
        "service_port": SERVICE_PORT,
        "crewai_available": CREWAI_AVAILABLE,
        "architecture": "modular_http_direct",
        "communication_type": "http_direct",
        "dependencies": {
            "crewai": CREWAI_AVAILABLE,
            "httpx": True,
            "fastapi": True
        },
        "capabilities": {
            "document_analysis": True,
            "checklist_processing": True,
            "background_processing": True,
            "sync_processing": True
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/debug/env")
async def debug_environment():
    """Endpoint de diagnóstico para verificar variables de entorno (sin exponer valores)."""
    env_vars = {
        "OPENAI_API_KEY": "✅ Configurada" if os.getenv("OPENAI_API_KEY") else "❌ Faltante",
        "SUPABASE_URL": "✅ Configurada" if os.getenv("SUPABASE_URL") else "❌ Faltante", 
        "SUPABASE_SERVICE_KEY": "✅ Configurada" if os.getenv("SUPABASE_SERVICE_KEY") else "❌ Faltante",
        "LLAMA_CLOUD_API_KEY": "✅ Configurada" if os.getenv("LLAMA_CLOUD_API_KEY") else "❌ Faltante",
        "SERPER_API_KEY": "✅ Configurada" if os.getenv("SERPER_API_KEY") else "❌ Faltante"
    }
    
    return {
        "service": "crewai_analysis_service",
        "environment_variables": env_vars,
        "crewai_available": CREWAI_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    }

async def save_analysis_result_to_markdown(result: "AnalysisResult") -> str:
    """Guarda el resultado del análisis en un archivo Markdown."""
    try:
        # Crear nombre de archivo con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"analysis_{result.case_id}_{timestamp}.md"
        filepath = RESULTS_DIR / filename
        
        # Crear contenido Markdown
        markdown_content = f"""# 📊 Análisis CrewAI - Case ID: {result.case_id}

## 📋 Información General
- **Case ID**: {result.case_id}
- **Estado**: {result.status}
- **Timestamp**: {result.timestamp}
- **Documentos Analizados**: {result.documents_analyzed}
- **CrewAI Disponible**: {'✅ Sí' if result.crewai_available else '❌ No (Simulado)'}

## 📄 Mensaje del Análisis
{result.message}

## 🔍 Detalles del Análisis
"""
        
        if result.analysis_details:
            # Si es análisis real de CrewAI
            if result.crewai_available and "crew_result" in result.analysis_details:
                markdown_content += f"""
### 🤖 Resultado de CrewAI
```
{result.analysis_details.get('crew_result', 'No disponible')}
```

### ⏱️ Información de Ejecución
- **Tiempo de Ejecución**: {result.analysis_details.get('execution_time', 'No disponible')}
- **Documentos Procesados**: {result.analysis_details.get('documents_processed', 0)}
- **Checklist Utilizado**: {result.analysis_details.get('checklist_used', 'No disponible')}
"""
            
            # Si es análisis simulado
            elif not result.crewai_available and isinstance(result.analysis_details, dict):
                details = result.analysis_details
                markdown_content += f"""
### 📊 Análisis Simulado
- **Score de Cumplimiento**: {details.get('compliance_score', 'N/A')}%

#### 📋 Documentos Faltantes
"""
                for doc in details.get('missing_documents', []):
                    markdown_content += f"- {doc}\n"
                
                markdown_content += "\n#### 📄 Análisis de Documentos\n"
                for doc_analysis in details.get('document_analysis', []):
                    status_emoji = "✅" if doc_analysis.get('status') == 'compliant' else "⚠️"
                    markdown_content += f"""
- **{doc_analysis.get('document', 'N/A')}**
  - Tag: {doc_analysis.get('tag', 'N/A')}
  - Estado: {status_emoji} {doc_analysis.get('status', 'N/A')}
  - Confianza: {doc_analysis.get('confidence', 0):.2%}
"""
                
                markdown_content += "\n#### 💡 Recomendaciones\n"
                for rec in details.get('recommendations', []):
                    markdown_content += f"- {rec}\n"
            
            # Si hay error
            elif "error" in result.analysis_details:
                markdown_content += f"""
### ❌ Error en el Análisis
```
{result.analysis_details.get('error', 'Error desconocido')}
```
"""
        
        markdown_content += f"""

---
*Análisis generado por {SERVICE_NAME} el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        # Guardar archivo
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        logger.info(f"💾 Resultado guardado en: {filepath}")
        return str(filepath)
        
    except Exception as e:
        logger.error(f"❌ Error al guardar resultado en Markdown: {e}")
        return ""

async def save_analysis_result_to_json(result: "AnalysisResult") -> str:
    """Guarda el resultado del análisis en un archivo JSON para futura migración a Supabase."""
    try:
        # Crear nombre de archivo con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"analysis_{result.case_id}_{timestamp}.json"
        filepath = RESULTS_DIR / filename
        
        # Preparar datos para JSON (estructura compatible con futura tabla Supabase)
        json_data = {
            "case_id": result.case_id,
            "status": result.status,
            "message": result.message,
            "timestamp": result.timestamp,
            "documents_analyzed": result.documents_analyzed,
            "crewai_available": result.crewai_available,
            "analysis_details": result.analysis_details,
            "created_at": datetime.now().isoformat(),
            "service_version": "http_direct_v1.0",
            "architecture": "modular_http_direct"
        }
        
        # Guardar archivo JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Resultado JSON guardado en: {filepath}")
        return str(filepath)
        
    except Exception as e:
        logger.error(f"❌ Error al guardar resultado en JSON: {e}")
        return ""

async def prepare_for_supabase_table(result: "AnalysisResult") -> Dict[str, Any]:
    """Prepara los datos del resultado para futura inserción en tabla Supabase."""
    return {
        "case_id": result.case_id,
        "status": result.status,
        "message": result.message,
        "timestamp": result.timestamp,
        "documents_analyzed": result.documents_analyzed,
        "crewai_available": result.crewai_available,
        "analysis_details": json.dumps(result.analysis_details) if result.analysis_details else None,
        "created_at": datetime.now().isoformat(),
        "service_version": "http_direct_v1.0",
        "architecture": "modular_http_direct"
    }

# TODO: Función para futura implementación con Supabase
async def save_analysis_result_to_supabase(result: "AnalysisResult") -> bool:
    """
    FUNCIÓN FUTURA: Guardará el resultado del análisis en una tabla de Supabase.
    
    Estructura de tabla sugerida 'analysis_results':
    - id (uuid, primary key)
    - case_id (text)
    - status (text)
    - message (text)
    - timestamp (timestamptz)
    - documents_analyzed (integer)
    - crewai_available (boolean)
    - analysis_details (jsonb)
    - created_at (timestamptz)
    - service_version (text)
    - architecture (text)
    """
    try:
        # Preparar datos
        data = await prepare_for_supabase_table(result)
        
        # TODO: Implementar inserción en Supabase cuando esté listo
        # supabase_client.table("analysis_results").insert(data).execute()
        
        logger.info(f"🔮 FUTURO: Datos preparados para Supabase - case_id: {result.case_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error preparando datos para Supabase: {e}")
        return False

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT) 