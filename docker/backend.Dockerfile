# syntax=docker/dockerfile:1
# The serviceops-workbench API. The build context is the app's backend folder:
#   docker build -f docker/backend.Dockerfile -t serviceops-backend app/backend

FROM python:3.12.16-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# Packages first, so a code change doesn't reinstall them.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# A fixed, unprivileged user id. Kubernetes can only check runAsNonRoot
# against a number, not a name.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER 10001

EXPOSE 8000
# Exec form, so uvicorn is PID 1 and gets the stop signal itself.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
