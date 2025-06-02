# 🤖 Guía de Despliegue en Render - CrewAI Analysis Service

## 📋 Pasos para Desplegar

### 1. Crear Servicio en Render
1. Ve a [Render Dashboard](https://dashboard.render.com/)
2. Haz clic en "New +" → "Web Service"
3. Conecta este repositorio GitHub
4. Configura el servicio:
   - **Name**: `pipefy-crewai-analysis-modular`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`

### 2. Configurar Variables de Entorno
En la sección "Environment" de Render, agrega:

```
OPENAI_API_KEY=tu_openai_api_key_aqui
LLAMA_CLOUD_API_KEY=tu_llama_cloud_api_key_aqui
SERPER_API_KEY=tu_serper_api_key_aqui
SUPABASE_URL=tu_url_supabase_aqui
SUPABASE_SERVICE_KEY=tu_service_key_aqui
```

### 3. Verificar Despliegue
- Health Check: `GET https://pipefy-crewai-analysis-modular.onrender.com/health`
- Status: `GET https://pipefy-crewai-analysis-modular.onrender.com/status`

### 4. Probar Análisis
```bash
curl -X POST https://pipefy-crewai-analysis-modular.onrender.com/analyze/sync \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "test_123",
    "documents": [],
    "checklist_url": "https://example.com/checklist.pdf",
    "current_date": "2025-06-01"
  }'
```

## 🔗 Endpoints del Servicio
- **Análisis Async**: `POST /analyze`
- **Análisis Sync**: `POST /analyze/sync`
- **Health Check**: `GET /health`
- **Status**: `GET /status`
- **Root**: `GET /`

## 🤖 Características
- Agentes CrewAI especializados
- Análisis de conformidad documental
- Detección de riesgos y fraudes
- Guardado automático de resultados
- Comunicación HTTP directa

## 📊 Monitoreo
- Logs detallados en Render Dashboard
- Resultados guardados en archivos MD y JSON
- Preparado para integración con Supabase 