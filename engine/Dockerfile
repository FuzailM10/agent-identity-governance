FROM python:3.12-slim

WORKDIR /app

# Install deps first so Docker caches this layer when only app code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

# --reload = auto-restart on code changes (dev convenience).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
