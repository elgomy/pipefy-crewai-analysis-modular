FROM python:3.11-slim

# Configurar directorio de trabajo
WORKDIR /app

# Copiar requirements y instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código del servicio
COPY . .

# Crear directorio para resultados
RUN mkdir -p analysis_results

# Exponer puerto
EXPOSE 8002

# Comando para ejecutar el servicio
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002"] 