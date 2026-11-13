# A release with a bug that makes the backend crash on startup. CI deploys it on
# purpose, to prove the rollout stops and is rolled back while the previous
# release keeps serving.
ARG BASE=serviceops-backend:local
FROM ${BASE}
USER root
RUN echo 'raise RuntimeError("simulated bad release: crashes on startup")' >> app/main.py
USER 10001
