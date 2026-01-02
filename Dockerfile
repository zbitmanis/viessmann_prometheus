#FROM python:3.11-slim as builder
FROM python:3.11-alpine as builder
ENV PYTHONDONTWRITEBYTECODE 1

WORKDIR /app

#Create python venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt /app/requirements.txt
#Install dependencies using builder container to 
#to Reduce image footprint
RUN pip install -r requirements.txt

#FROM python:3.11-slim as runner
FROM python:3.11-alpine as runner
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV VIESSMANN_PORT 9000
ENV VIESSMANN_HOST 0.0.0.0

COPY viessmann_prometheus/ /app/viessmann_prometheus

EXPOSE 9000

CMD [ "uvicorn", "viessmann_prometheus.viessmann_prometheus:viessmann_prometheus","--host", "0.0.0.0", "--port", "9000", "--log-config /config/logging.yaml"]
