# R118 isolated 512 MiB admission soak image, NEVER deploy.
FROM python:3.11-slim
ARG FFH_TEST_TARGET
ARG FFH_TEST_BATCH=8
ARG FFH_TEST_BEAM=4
ENV ARGOS_DEVICE_TYPE=cpu \
    ARGOS_CHUNK_TYPE=MINISBD \
    ARGOS_COMPUTE_TYPE=int8 \
    ARGOS_INTER_THREADS=1 \
    ARGOS_INTRA_THREADS=1 \
    ARGOS_BATCH_SIZE=${FFH_TEST_BATCH} \
    ARGOS_BEAM_SIZE=${FFH_TEST_BEAM} \
    OMP_NUM_THREADS=1 \
    FFH_TARGET_LANGUAGE=${FFH_TEST_TARGET} \
    FFH_MULTILINGUAL=false \
    FFH_TRANSLATION_CACHE_ENABLED=false \
    FFH_GUARDED_API_STAGING_ONLY=true \
    PYTHONUNBUFFERED=1
WORKDIR /srv/ffh
COPY r109-light/ /tmp/r109-light/
COPY app.py install_models.py translation_cache.py protected_translation.py ./
COPY tests/r110_prefetch_minisbd.py tests/r110_prefetch_minisbd.py
COPY tests/r118_admission_soak.py tests/r118_admission_soak.py
RUN test -n "$FFH_TEST_TARGET" \
    && python -m pip install --no-cache-dir --disable-pip-version-check \
       /tmp/r109-light 'Flask>=3.1,<4' 'gunicorn>=23,<24' \
    && python -m pip check \
    && python install_models.py \
    && python tests/r110_prefetch_minisbd.py
CMD ["python", "tests/r118_admission_soak.py"]
