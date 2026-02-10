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

ARG VIESSMANN_PORT=9000
ARG VIESSMANN_HOST=0.0.0.0
ARG VIESSMANN_LOG_CONFIG=/config/logging.yaml

ENV VIESSMANN_PORT=${VIESSMANN_PORT}
ENV VIESSMANN_HOST=${VIESSMANN_HOST}
ENV VIESSMANN_LOG_CONFIG=${VIESSMANN_LOG_CONFIG}

COPY viessmann_prometheus/ /app/viessmann_prometheus

EXPOSE ${VIESSMANN_PORT}

CMD ["sh", "-c", "exec uvicorn viessmann_exporter.main:app \
    --host ${VIESSMANN_HOST} \
    --port ${VIESSMANN_PORT} \
    --log-config ${VIESSMANN_LOG_CONFIG}"]
