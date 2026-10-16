# R110: disposable test container only. NOT a production image.
FROM python:3.11-slim

ENV ARGOS_DEVICE_TYPE=cpu \
    ARGOS_CHUNK_TYPE=MINISBD \
    ARGOS_COMPUTE_TYPE=int8 \
    ARGOS_INTER_THREADS=1 \
    ARGOS_INTRA_THREADS=1 \
    ARGOS_BATCH_SIZE=8 \
    OMP_NUM_THREADS=1 \
    FFH_TARGET_LANGUAGE=es \
    FFH_MULTILINGUAL=false \
    FFH_TRANSLATION_CACHE_ENABLED=false \
    FFH_TEST_GUNICORN_THREADS=2 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/ffh
COPY r109-light/ /tmp/r109-light/
COPY app.py install_models.py translation_cache.py ./
COPY tests/r106_localhost_service.py tests/r106_localhost_service.py
COPY tests/r110_cgroup_assert.py tests/r110_cgroup_assert.py

RUN python -m pip install --no-cache-dir --disable-pip-version-check \
    /tmp/r109-light 'Flask>=3.1,<4' 'gunicorn>=23,<24' \
    && python -m pip check \
    && python install_models.py

CMD ["python", "tests/r110_cgroup_assert.py"]
