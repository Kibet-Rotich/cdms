FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# Migrate, seed demo data on first start (skipped if data exists), then serve.
# Proof of concept: Django dev server. For a real deployment use gunicorn + a static file server.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed_demo && python manage.py runserver 0.0.0.0:8000 --noreload"]
