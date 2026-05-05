FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .
COPY .env.example .

EXPOSE 8000

# Reintenta database_setup.py hasta que la BD esté lista,
# luego arranca uvicorn. $PORT lo asigna el cloud (Render, Railway…).
CMD ["sh", "-c", "\
  echo 'Esperando base de datos...' && \
  for i in 1 2 3 4 5 6 7 8 9 10; do \
    python database_setup.py && break; \
    echo \"Intento $i fallido, reintentando en 5s...\"; \
    sleep 5; \
  done && \
  echo 'Arrancando API...' && \
  uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000} \
"]
