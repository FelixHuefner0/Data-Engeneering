FROM apache/spark-py:v3.4.0

USER root

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
#RUN python database/init_db.py

EXPOSE 8501

CMD ["python3", "main.py"]
