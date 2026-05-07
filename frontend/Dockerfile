FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r app && useradd -r -g app -d /home/app -m app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

USER app

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
