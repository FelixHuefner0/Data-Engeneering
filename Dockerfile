FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unzip

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app    
RUN python database/init_db.py

# Expose Streamlit port
EXPOSE 8501

CMD ["streamlit", "run", "src/streamlit_test.py", "--server.port=8501", "--server.address=0.0.0.0"]
