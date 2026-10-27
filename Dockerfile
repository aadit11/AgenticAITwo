# Multi-stage image. Dependencies install into /usr/local, which appuser can read.
# The syllabus sketch that copies into /root/.local and then switches user does not.

FROM python:3.13-slim AS build

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.13-slim

RUN useradd --create-home --uid 1000 appuser

COPY --from=build /install /usr/local

WORKDIR /app

COPY main.py .
COPY app ./app
COPY tools ./tools
COPY static ./static
COPY code_bundle ./code_bundle
COPY chroma_index ./chroma_index
COPY data ./data

RUN chown -R appuser:appuser /app

USER appuser

ENV PORT=8080 \
    PYTHONUNBUFFERED=1 \
    CHROMA_PERSIST_DIR=./chroma_index \
    SQLITE_PATH=./data/peps.sqlite \
    CODE_BUNDLE_DIR=./code_bundle

EXPOSE 8080

CMD ["sh", "-c", "exec python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
