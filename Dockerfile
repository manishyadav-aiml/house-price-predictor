FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-app.txt .
RUN pip install --no-cache-dir -r requirements-app.txt
COPY . .
RUN useradd -m appuser && chown -R appuser /app
USER appuser
EXPOSE 8000
# SECRET_KEY must be provided at run time:  docker run -e SECRET_KEY=... -p 8000:8000 image
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "app:app"]
