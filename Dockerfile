FROM python:3.11-slim

WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app code
COPY . .

# non-root user
RUN useradd -m -u 1000 trader && chown -R trader:trader /app
USER trader

# start app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
