# R125 DISPOSABLE TWO-MODEL SERIAL SWITCH TEST. NEVER DEPLOY.
# One image contains both language packages on DISK; only one backend process
# may run, and only one model directory is mounted at the app's model path.
FROM python:3.11-slim
ENV ARGOS_DEVICE_TYPE=cpu \
    ARGOS_CHUNK_TYPE=MINISBD \
    ARGOS_COMPUTE_TYPE=int8 \
    ARGOS_INTER_THREADS=1 \
    ARGOS_INTRA_THREADS=1 \
    OMP_NUM_THREADS=1 \
    FFH_MULTILINGUAL=false \
    FFH_TRANSLATION_CACHE_ENABLED=false \
    FFH_GUARDED_API_STAGING_ONLY=true \
    FFH_LEGACY_QUARANTINE_STAGING_ONLY=true \
    PYTHONUNBUFFERED=1
WORKDIR /srv/ffh
COPY r109-light/ /tmp/r109-light/
COPY app.py install_models.py translation_cache.py protected_translation.py ./
COPY tests/r110_prefetch_minisbd.py tests/r110_prefetch_minisbd.py
COPY tests/r125_serial_gateway.py tests/r125_serial_gateway.py
COPY tests/r125_serial_switch.py tests/r125_serial_switch.py
COPY tests/r123h_memory_policy.py tests/r123h_memory_policy.py
COPY models/r119_observed_model_trees.json models/r119_observed_model_trees.json
COPY tools/r119_verify_model_tree.py tools/r119_verify_model_tree.py
RUN python -m pip install --no-cache-dir --disable-pip-version-check \
        /tmp/r109-light 'Flask>=3.1,<4' 'gunicorn>=23,<24' \
    && python -m pip check \
    && python tests/r110_prefetch_minisbd.py
RUN mkdir -p /srv/ffh/r125-models \
    && FFH_TARGET_LANGUAGE=es python install_models.py \
    && FFH_TARGET_LANGUAGE=es python tools/r119_verify_model_tree.py \
    && mv /srv/ffh/.argos/packages /srv/ffh/r125-models/es \
    && FFH_TARGET_LANGUAGE=fr python install_models.py \
    && FFH_TARGET_LANGUAGE=fr python tools/r119_verify_model_tree.py \
    && mv /srv/ffh/.argos/packages /srv/ffh/r125-models/fr \
    && ln -s /srv/ffh/r125-models/es /srv/ffh/.argos/packages
CMD ["python", "tests/r125_serial_switch.py"]
