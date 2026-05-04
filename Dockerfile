FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias primero (mejor uso de caché de capas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY *.py .
COPY .env.example .

EXPOSE 8000

# En Railway $PORT es asignado automáticamente.
# database_setup.py inicializa las tablas si no existen (idempotente).
CMD ["sh", "-c", "python database_setup.py && uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
