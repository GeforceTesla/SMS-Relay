FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --system --create-home --home-dir /nonexistent --shell /usr/sbin/nologin smsrelay

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app app

USER smsrelay

EXPOSE 8000 8001

CMD ["uvicorn", "app.main:public_app", "--host", "0.0.0.0", "--port", "8000"]
