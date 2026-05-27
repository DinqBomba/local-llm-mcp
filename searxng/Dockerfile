FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY searxng_mcp.py .

CMD ["python", "searxng_mcp.py"]
