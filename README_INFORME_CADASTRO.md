# 📊 Módulo CrewAI - Sistema de Informes de Cadastro (Arquitectura Modular)

## 🎯 **ARQUITECTURA MODULAR IMPLEMENTADA**

### ✅ **1. Nueva Tabla `informe_cadastro`**

Se creó una tabla específica para almacenar los informes generados por la crew de CrewAI:

```sql
CREATE TABLE public.informe_cadastro (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id TEXT NOT NULL,                    -- ID del cliente/caso
    informe TEXT NOT NULL,                    -- Informe completo en markdown
    risk_score TEXT,                          -- Score categórico (Alto, Médio, Baixo)
    risk_score_numeric INTEGER,               -- Score numérico (0-100)
    summary_report TEXT,                      -- Resumen para sistemas externos
    documents_analyzed INTEGER DEFAULT 0,     -- Número de documentos analizados
    crewai_available BOOLEAN DEFAULT true,    -- Si CrewAI estaba disponible
    analysis_details JSONB,                  -- Detalles adicionales en JSON
    status TEXT DEFAULT 'completed',          -- Estado del análisis
    created_at TIMESTAMPTZ DEFAULT NOW(),     -- Fecha de creación
    updated_at TIMESTAMPTZ DEFAULT NOW()      -- Fecha de actualización
);
```

### ✅ **2. Eliminación de Columna Obsoleta**

Se eliminó la columna `crew_analysis_result` de la tabla `documents` para mantener la separación de responsabilidades.

### ✅ **3. Integración con Supabase**

- **Cliente Supabase**: Inicialización automática del cliente
- **Guardado Automático**: Los informes se guardan automáticamente en Supabase
- **Manejo de Errores**: Gestión robusta de errores de conexión

### ✅ **4. Arquitectura Event-Driven con Webhooks de Supabase**

**MODULARIDAD MÁXIMA**: El módulo CrewAI se enfoca ÚNICAMENTE en análisis. La integración con sistemas externos se maneja mediante webhooks de Supabase:

- **Webhook Automático**: Cuando se crea un registro en `informe_cadastro`, Supabase dispara automáticamente un webhook
- **Desacoplamiento Total**: CrewAI no tiene dependencias de Pipefy u otros sistemas externos
- **Event-Driven**: El módulo de ingestión recibe el webhook y actualiza Pipefy
- **Escalabilidad**: Fácil agregar nuevas integraciones sin modificar CrewAI

### ✅ **5. Extracción Inteligente de Risk Score**

Función que analiza el resultado de CrewAI para extraer automáticamente:
- **Score Categórico**: Alto, Médio, Baixo
- **Score Numérico**: 0-100

### ✅ **6. Generación de Resúmenes**

Función que genera resúmenes concisos para sistemas externos (máximo 450 caracteres).

### ✅ **7. Endpoints de Consulta**

- `GET /informes` - Lista todos los informes guardados
- `GET /informe/{case_id}` - Consulta informe específico por case_id
- `GET /status` - Estado del servicio con información de integraciones
- `POST /analyze` - Análisis asíncrono de documentos
- `POST /analyze/sync` - Análisis síncrono de documentos

## 🔧 **CONFIGURACIÓN REQUERIDA**

### Variables de Entorno (Solo para CrewAI)

```bash
# Supabase
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_KEY=your-service-key-here

# OpenAI
OPENAI_API_KEY=your-openai-api-key-here

# LlamaParse
LLAMA_CLOUD_API_KEY=your-llama-cloud-api-key-here

# Servicio
CREWAI_SERVICE_PORT=8002
```

**NOTA**: Las variables de Pipefy se configuran en el módulo de ingestión, NO en CrewAI.

## 📊 **FLUJO DE DATOS MODULAR**

```
1. Webhook Pipefy → Módulo A (Ingestión)
2. Documentos → Supabase Storage + Tabla 'documents'
3. Módulo A → Llama Módulo B (CrewAI) vía HTTP
4. Módulo B → Analiza documentos con CrewAI + checklist parseado
5. Módulo B → Extrae risk_score automáticamente
6. Módulo B → Genera resumen para sistemas externos
7. Módulo B → Guarda informe en tabla 'informe_cadastro'
8. Supabase → Detecta INSERT y dispara webhook automático
9. Módulo A → Recibe webhook y actualiza Pipefy
```

## 🏗️ **PRINCIPIOS DE MODULARIDAD APLICADOS**

### 🎯 **Responsabilidad Única**
- **Módulo CrewAI**: Solo análisis de documentos
- **Módulo Ingestión**: Solo manejo de webhooks y integraciones externas
- **Supabase**: Solo almacenamiento y eventos

### 🔗 **Bajo Acoplamiento**
- CrewAI no conoce Pipefy ni otros sistemas externos
- Comunicación vía HTTP y eventos de base de datos
- Cada módulo puede evolucionar independientemente

### 📈 **Alta Cohesión**
- Cada módulo agrupa funcionalidades relacionadas
- Interfaces claras entre módulos
- Fácil testing y mantenimiento

## 🔍 **ESTRUCTURA DEL INFORME**

Cada informe guardado contiene:

- **case_id**: Vinculado con la tabla `documents`
- **informe**: Análisis completo en formato markdown
- **risk_score**: Categorización del riesgo
- **risk_score_numeric**: Valor numérico para ordenamiento
- **summary_report**: Resumen para sistemas externos
- **analysis_details**: Metadatos del análisis en JSON

## 🚀 **BENEFICIOS DE LA ARQUITECTURA MODULAR**

1. **Separación de Responsabilidades**: Cada módulo tiene una función específica
2. **Escalabilidad**: Fácil agregar nuevos tipos de análisis o integraciones
3. **Mantenibilidad**: Cambios en un módulo no afectan al otro
4. **Trazabilidad**: Historial completo de análisis por cliente
5. **Flexibilidad**: Diferentes formatos de salida según necesidad
6. **Desacoplamiento**: Cero dependencias entre módulos
7. **Event-Driven**: Arquitectura reactiva y asíncrona

## 📈 **PRÓXIMOS PASOS SUGERIDOS**

1. **Dashboard de Informes**: Crear interfaz para visualizar informes
2. **Nuevas Integraciones**: Agregar webhooks para otros sistemas
3. **Métricas**: Análisis de tendencias de risk scores
4. **Validaciones**: Reglas de negocio adicionales
5. **Exportación**: Generar PDFs de informes

## 🔧 **COMANDOS ÚTILES**

```bash
# Consultar todos los informes
curl http://localhost:8002/informes

# Consultar informe específico
curl http://localhost:8002/informe/CASE_ID_123

# Estado del servicio
curl http://localhost:8002/status

# Análisis asíncrono
curl -X POST http://localhost:8002/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "CASE_123",
    "documents": [...],
    "checklist_url": "...",
    "current_date": "2024-01-15"
  }'

# Análisis síncrono
curl -X POST http://localhost:8002/analyze/sync \
  -H "Content-Type: application/json" \
  -d '{...}'
```

## 🔄 **Webhook de Supabase**

El webhook se configura automáticamente para disparar cuando se inserta un nuevo registro en `informe_cadastro`:

```sql
-- Función que se ejecuta automáticamente
CREATE OR REPLACE FUNCTION notify_informe_created()
RETURNS TRIGGER AS $$
BEGIN
  PERFORM net.http_post(
    url := 'https://pipefy-document-ingestion-modular.onrender.com/webhook/supabase/informe-created',
    headers := '{"Content-Type": "application/json"}'::jsonb,
    body := json_build_object(
      'type', 'INSERT',
      'table', 'informe_cadastro',
      'record', row_to_json(NEW)
    )::text
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger que dispara automáticamente
CREATE TRIGGER trigger_informe_cadastro_webhook
  AFTER INSERT ON informe_cadastro
  FOR EACH ROW
  EXECUTE FUNCTION notify_informe_created();
```

---

*Documentación actualizada - Arquitectura Modular Event-Driven* 