# R113 test-only matrix image: one model per memory-constrained container.
FROM python:3.11-slim
ARG FFH_TEST_TARGET
ENV ARGOS_DEVICE_TYPE=cpu \
    ARGOS_CHUNK_TYPE=MINISBD \
    ARGOS_COMPUTE_TYPE=int8 \
    ARGOS_INTER_THREADS=1 \
    ARGOS_INTRA_THREADS=1 \
    ARGOS_BATCH_SIZE=8 \
    OMP_NUM_THREADS=1 \
    FFH_TARGET_LANGUAGE=${FFH_TEST_TARGET} \
    FFH_MULTILINGUAL=false \
    FFH_TRANSLATION_CACHE_ENABLED=false \
    PYTHONUNBUFFERED=1
WORKDIR /srv/ffh
COPY r109-light/ /tmp/r109-light/
COPY app.py install_models.py translation_cache.py ./
COPY tests/r110_prefetch_minisbd.py tests/r110_prefetch_minisbd.py
COPY tests/r113_single_model_matrix.py tests/r113_single_model_matrix.py
RUN test -n "$FFH_TEST_TARGET" \
    && python -m pip install --no-cache-dir --disable-pip-version-check \
      /tmp/r109-light 'Flask>=3.1,<4' 'gunicorn>=23,<24' \
    && python -m pip check \
    && python install_models.py \
    && python tests/r110_prefetch_minisbd.py
CMD ["python", "tests/r113_single_model_matrix.py"]
