FROM python:3.8-slim as base

ENV PATH "/opt/venv/bin:$PATH"
ENV PIP_DISABLE_PIP_VERSION_CHECK 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

FROM base as builder
RUN python -m venv /opt/venv
RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install --requirement requirements.txt

FROM base
RUN apt-get update
RUN apt-get install -y libjemalloc2
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY *.py .
ENV LD_PRELOAD /usr/lib/x86_64-linux-gnu/libjemalloc.so.2
EXPOSE 8000

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 app:app
