<<<<<<< HEAD
# 🤖 CrewAI Analysis Service

Servicio modular para análisis de documentos usando CrewAI con comunicación HTTP directa.

## 🏗️ Arquitectura

- **Responsabilidad**: Analizar documentos usando agentes CrewAI especializados
- **Comunicación**: HTTP directa, recibe llamadas del servicio de ingestión
- **Puerto**: 8002
- **Modularidad**: Servicio independiente y especializado

## 🚀 Despliegue en Render

### Variables de Entorno Requeridas:
- `OPENAI_API_KEY`: API key de OpenAI para los LLMs
- `LLAMA_CLOUD_API_KEY`: API key de LlamaCloud para parsing (opcional)
- `SERPER_API_KEY`: API key de Serper para búsquedas web (opcional)
- `SUPABASE_URL`: URL de Supabase para acceso a documentos
- `SUPABASE_SERVICE_KEY`: Service key de Supabase

### Comando de Inicio:
```bash
uvicorn api_http_direct:app --host 0.0.0.0 --port $PORT
```

## 📋 Endpoints

- `POST /analyze` - Análisis asíncrono de documentos
- `POST /analyze/sync` - Análisis síncrono de documentos
- `GET /health` - Health check
- `GET /status` - Estado detallado del servicio
- `GET /` - Información del servicio

## 🤖 Agentes CrewAI

1. **Especialista en Conformidade Documental**: Valida documentos contra checklist
2. **Detetive de Dados Corporativos**: Extrae información estructurada
3. **Investigador Corporativo Sênior**: Análisis de riesgo y recomendaciones

## 💾 Resultados

Los análisis se guardan automáticamente en:
- **Archivos Markdown**: Para lectura humana (`analysis_results/*.md`)
- **Archivos JSON**: Para procesamiento programático (`analysis_results/*.json`)
- **Preparación Supabase**: Estructura lista para tabla `analysis_results`

## 🔗 Comunicación

Este servicio:
- **Recibe**: Llamadas HTTP del servicio de ingestión
- **Accede**: Documentos almacenados en Supabase
- **Utiliza**: APIs externas (OpenAI, LlamaCloud, Serper)

## 📦 Dependencias

Ver `requirements.txt` para la lista completa de dependencias incluyendo CrewAI, LangChain y herramientas especializadas. 
=======
# pipefy-crewai-analysis-modular
🤖 Servicio modular CrewAI para análisis inteligente de documentos
>>>>>>> fa681ad931275845faf8c6b9d5b555b591059622
