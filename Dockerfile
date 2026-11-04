FROM python:3.12-alpine
RUN apk add --no-cache git tzdata && addgroup -g 1000 nullgate && adduser -D -u 1000 -G nullgate nullgate
WORKDIR /app
COPY . /app
COPY scripts/supervisor.py /opt/null_gate-supervisor.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data PORT=8088 INSTALL_METHOD=docker
RUN mkdir -p /data && chown -R nullgate:nullgate /app /data
USER nullgate
EXPOSE 8088
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8088')+'/api/health',timeout=3)"
CMD ["python", "/opt/null_gate-supervisor.py"]
