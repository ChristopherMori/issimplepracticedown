FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir requests pytz flask pyyaml
CMD ["python", "check_status.py"]
