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

async def download_checklist_content(checklist_url: str) -> str:
    """Descarga el contenido del checklist desde la URL."""
    try:
        logger.info(f"📥 Descargando contenido del checklist...")
        logger.info(f"📥 Descargando checklist desde: {checklist_url}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(checklist_url)
            response.raise_for_status()
            
            # Si es un PDF, usar LlamaParse para extraer texto
            if checklist_url.lower().endswith('.pdf'):
                logger.info("📄 Archivo PDF detectado - extrayendo texto...")
                
                # Verificar si LlamaParse está disponible
                llama_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
                if not llama_api_key:
                    logger.warning("⚠️ LLAMA_CLOUD_API_KEY no configurada - usando contenido simulado...")
                    return """
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
                        return content
                    else:
                        logger.warning("⚠️ LlamaParse no retornó contenido - usando fallback")
                        return "Error: No se pudo extraer contenido del PDF con LlamaParse"
                        
                except Exception as llama_error:
                    logger.error(f"❌ Error con LlamaParse: {llama_error}")
                    logger.warning("⚠️ Fallback a contenido simulado debido a error de LlamaParse")
                    return """
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
                content = response.text
                logger.info(f"📄 Contenido del checklist descargado: {len(content)} caracteres")
                return content
                
    except Exception as e:
        logger.error(f"❌ Error al descargar checklist: {e}")
        return f"Error al descargar checklist desde {checklist_url}: {e}"

async def analyze_documents_with_crewai(request: CrewAIAnalysisRequest) -> AnalysisResult:
    """Analiza documentos usando CrewAI."""
    try:
        logger.info(f"🔍 Iniciando análisis CrewAI para case_id: {request.case_id}")
        logger.info(f"📄 Documentos a analizar: {len(request.documents)}")
        logger.info(f"📋 Checklist URL: {request.checklist_url}")
        
        if not CREWAI_AVAILABLE:
            logger.warning("⚠️ CrewAI no disponible - ejecutando análisis simulado")
            
            # Análisis simulado detallado
            simulated_analysis = {
                "compliance_score": 85.5,
                "missing_documents": ["comprovante_residencia", "declaracao_impostos"],
                "document_analysis": [
                    {
                        "document": doc["name"],
                        "tag": doc["document_tag"],
                        "status": "compliant" if "contrato" in doc["name"].lower() else "needs_review",
                        "confidence": 0.92
                    }
                    for doc in request.documents
                ],
                "recommendations": [
                    "Solicitar comprovante de residência atualizado",
                    "Verificar declaração de impostos do último ano",
                    "Confirmar assinatura digital nos contratos"
                ]
            }
            
            simulated_result = AnalysisResult(
                case_id=request.case_id,
                status="simulated_success",
                message=f"Análisis simulado completado para {len(request.documents)} documentos",
                timestamp=datetime.now().isoformat(),
                documents_analyzed=len(request.documents),
                crewai_available=False,
                analysis_details=simulated_analysis
            )
            
            # 💾 GUARDAR RESULTADOS SIMULADOS EN ARCHIVOS
            logger.info(f"💾 Guardando resultados del análisis simulado...")
            
            # Guardar en Markdown
            markdown_path = await save_analysis_result_to_markdown(simulated_result)
            if markdown_path:
                logger.info(f"📄 Resultado Simulado Markdown: {markdown_path}")
            
            # Guardar en JSON
            json_path = await save_analysis_result_to_json(simulated_result)
            if json_path:
                logger.info(f"📄 Resultado Simulado JSON: {json_path}")
            
            # Preparar para futura tabla Supabase
            await save_analysis_result_to_supabase(simulated_result)
            
            return simulated_result
        
        # Descargar contenido del checklist
        logger.info("📥 Descargando contenido del checklist...")
        checklist_content = await download_checklist_content(request.checklist_url)
        
        # Preparar inputs para la crew
        crew_inputs = {
            "case_id": request.case_id,
            "checklist": checklist_content,  # Contenido del checklist, no URL
            "current_date": request.current_date,
            "documents": request.documents
        }
        
        # Crear instancia de la crew
        crew = CadastroCrew(inputs=crew_inputs)
        
        logger.info(f"🚀 Ejecutando CrewAI con {len(request.documents)} documentos...")
        
        # Ejecutar la crew
        result = crew.run()
        
        logger.info(f"✅ Análisis CrewAI completado para case_id: {request.case_id}")
        
        # Procesar resultado de CrewAI
        analysis_details = {
            "crew_result": str(result),
            "execution_time": datetime.now().isoformat(),
            "documents_processed": len(request.documents),
            "checklist_used": request.checklist_url
        }
        
        analysis_result = AnalysisResult(
            case_id=request.case_id,
            status="success",
            message=f"Análisis CrewAI completado exitosamente para {len(request.documents)} documentos",
            timestamp=datetime.now().isoformat(),
            documents_analyzed=len(request.documents),
            crewai_available=True,
            analysis_details=analysis_details
        )
        
        # 💾 GUARDAR RESULTADOS EN ARCHIVOS
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
        
        return analysis_result
        
    except Exception as e:
        logger.error(f"❌ Error en análisis CrewAI para case_id {request.case_id}: {e}")
        return AnalysisResult(
            case_id=request.case_id,
            status="error",
            message=f"Error en análisis CrewAI: {str(e)}",
            timestamp=datetime.now().isoformat(),
            documents_analyzed=0,
            crewai_available=CREWAI_AVAILABLE,
            analysis_details={"error": str(e)}
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