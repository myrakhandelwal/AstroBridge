# AstroBridge: Deployment & Production Guide

## Table of Contents

1. [Deployment Strategies](#deployment-strategies)
2. [Local Development Setup](#local-development-setup)
3. [Docker Deployment](#docker-deployment)
4. [Cloud Deployment (AWS)](#cloud-deployment-aws)
5. [PyPI Release & Distribution](#pypi-release--distribution)
6. [Production Configuration](#production-configuration)
7. [Database Setup & Migration](#database-setup--migration)
8. [Monitoring & Observability](#monitoring--observability)
9. [Security & Hardening](#security--hardening)
10. [Troubleshooting Deployments](#troubleshooting-deployments)
11. [Performance Tuning](#performance-tuning)
12. [Disaster Recovery](#disaster-recovery)

---

## Deployment Strategies

AstroBridge supports three deployment architectures:

### 1. **Single-Machine (Development/Small Teams)**
- CLI-only on developer laptops
- Optional web UI for interactive use
- Local SQLite state storage
- Suitable for: Research projects, teaching, prototyping

### 2. **Docker Container (Standardized)**
- Docker image with FastAPI web console
- Volume-mounted state directory
- Container orchestration (Docker Compose, Kubernetes)
- Suitable for: Institutional deployments, shared resources

### 3. **Cloud-Native (High Scale)**
- AWS Lambda/Fargate serverless
- Managed databases (RDS for SQLite migration to PostgreSQL)
- Load balancing (ALB)
- API Gateway for REST endpoints
- Suitable for: Public APIs, production science platforms

---

## Local Development Setup

### Prerequisites

```bash
# macOS
brew install python@3.9 git

# Ubuntu/Debian
sudo apt-get install python3.9 python3.9-venv python3-pip

# Verify
python3.9 --version  # Should be 3.9.x or later
```

### Installation

```bash
# Clone repository
git clone https://github.com/myrakhandelwal/AstroBridge.git
cd AstroBridge

# Create virtual environment
python3.9 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# -or-
.venv\Scripts\activate     # Windows

# Install in development mode with PEP 621 pyproject.toml
pip install -e .[dev]      # Includes pytest, mypy, ruff 
pip install -e .[web]      # Optional: FastAPI + web UI
pip install -e .[live]     # Optional: Live TAP adapters (pyvo, etc)

# Verify installation
python -c "import astrobridge; print(f'AstroBridge {astrobridge.__version__}')"
pytest --version
ruff --version
mypy --version
```

### Version Management

**Automated via setuptools_scm**: Versions are derived from git tags. No manual version edits needed.

```bash
# Current stable version
git tag  # Lists all tags, e.g., v0.3.0

# To create a new release
git tag -a v0.3.1 -m "Release message"
git push --tags
# Version auto-generates in _version.py at build time
```

### Development Workflow

```bash
# Run tests
pytest tests/ -v                 # All 148 tests
pytest tests/test_matcher.py -v  # Single test module

# Modern linting with Ruff
ruff check .                      # Lint checks (E, F, I, UP, B, SIM)
ruff check . --fix                # Auto-fix violations

# Type checking (strict on core modules)
mypy astrobridge/connectors.py    # Strict on core
mypy astrobridge/                 # Relaxed on library modules

# All quality gates at once
ruff check . && mypy astrobridge && pytest -q

# Run demo
python demo.py                    # End-to-end demo
astrobridge-demo                  # Via entry point
```
python demo.py                    # End-to-end demo
astrobridge-demo                  # Via entry point
```

### CI/CD Pipeline

**GitHub Actions** automates quality checks on every PR and push:

```yaml
# .github/workflows/ci.yml structure:
1. Ruff lint checks (import sorting, type upgrades, style rules)
2. Mypy strict type checking (core modules: connectors, orchestrator, jobs)
3. Pytest full test suite (148 tests, async mode, 0 warnings)
```

**Local validation** before pushing:

```bash
# Run all checks locally (same as CI)
ruff check . && mypy astrobridge && pytest -q

# Auto-fix Ruff violations
ruff check . --fix --unsafe

# Check specific modules with strict mypy
mypy --strict astrobridge/connectors.py
mypy --strict astrobridge/api/orchestrator.py
mypy --strict astrobridge/jobs.py
```

All commits must pass these gates. CI pipeline ensures production-ready code.

### Environment Variables

```bash
# Database location (default: .astrobridge/state.db)
export ASTROBRIDGE_STATE_DB=/path/to/state.db

# Logging level (DEBUG, INFO, WARNING, ERROR)
export LOGLEVEL=DEBUG

# API configuration
export FASTAPI_ENV=development
export FASTAPI_HOST=0.0.0.0
export FASTAPI_PORT=8000
```

---

## Docker Deployment

### Dockerfile

A production-ready Dockerfile is included in the repository:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy code
COPY . /app

# Install AstroBridge
RUN pip install --no-cache-dir -e .[web,live]

# Create state directory
RUN mkdir -p /data/astrobridge

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Start web server
ENV ASTROBRIDGE_STATE_DB=/data/astrobridge/state.db
CMD ["astrobridge-web"]
```

### Build & Run

```bash
# Build image
docker build -t astrobridge:0.3.0 .

# Run container
docker run \
  -p 8000:8000 \
  -v astrobridge_data:/data/astrobridge \
  astrobridge:0.3.0

# Access web UI
open http://localhost:8000
```

### Docker Compose

For multi-service deployments:

```yaml
version: '3.8'

services:
  astrobridge:
    build: .
    image: astrobridge:0.2.0
    ports:
      - "8000:8000"
    volumes:
      - astrobridge_data:/data/astrobridge
    environment:
      ASTROBRIDGE_STATE_DB: /data/astrobridge/state.db
      LOGLEVEL: INFO
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Optional: PostgreSQL for production state storage
  postgres:
    image: postgres:14-alpine
    environment:
      POSTGRES_USER: astrobridge
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: astrobridge_state
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  astrobridge_data:
  postgres_data:
```

### Deploy with Docker Compose

```bash
# Start services
docker-compose up -d

# Check logs
docker-compose logs -f astrobridge

# Stop services
docker-compose down
```

---

## Cloud Deployment (AWS)

### Option 1: Elastic Container Service (ECS)

**Architecture**: Fargate (serverless containers) + ALB (load balancing) + RDS (PostgreSQL)

#### Step 1: Create ECR Repository

```bash
aws ecr create-repository --repository-name astrobridge --region us-east-1

# Push image
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com

docker tag astrobridge:0.2.0 123456789.dkr.ecr.us-east-1.amazonaws.com/astrobridge:0.2.0
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/astrobridge:0.2.0
```

#### Step 2: Create RDS PostgreSQL Database

```bash
aws rds create-db-instance \
  --db-instance-identifier astrobridge-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username astrobridge \
  --master-user-password "${POSTGRES_PASSWORD}" \
  --allocated-storage 20 \
  --publicly-accessible false
```

#### Step 3: Create ECS Cluster & Task Definition

```bash
# Create cluster
aws ecs create-cluster --cluster-name astrobridge-prod

# Register task definition (JSON file)
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

**task-definition.json**:
```json
{
  "family": "astrobridge-web",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "astrobridge",
      "image": "123456789.dkr.ecr.us-east-1.amazonaws.com/astrobridge:0.2.0",
      "portMappings": [
        {
          "containerPort": 8000,
          "hostPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ASTROBRIDGE_STATE_DB",
          "value": "postgresql://astrobridge:password@astrobridge-db.xxx.rds.amazonaws.com:5432/astrobridge_state"
        },
        {
          "name": "LOGLEVEL",
          "value": "INFO"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/astrobridge-web",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### Step 4: Create Application Load Balancer

```bash
# Create ALB
aws elbv2 create-load-balancer \
  --name astrobridge-alb \
  --subnets subnet-12345678 subnet-87654321

# Create target group
aws elbv2 create-target-group \
  --name astrobridge-targets \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-12345678 \
  --health-check-path /health
```

#### Step 5: Create ECS Service

```bash
aws ecs create-service \
  --cluster astrobridge-prod \
  --service-name astrobridge-web \
  --task-definition astrobridge-web \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-12345678,subnet-87654321],securityGroups=[sg-12345678],assignPublicIp=ENABLED}" \
  --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=astrobridge,containerPort=8000
```

### Option 2: Lambda + API Gateway

For serverless REST API:

```python
# lambda_handler.py
from mangum import Mangum
from astrobridge.web.app import app

handler = Mangum(app, lifespan="off")
```

Deploy:
```bash
# Package
pip install -r requirements.txt -t package/
cp lambda_handler.py package/
cd package && zip -r ../astrobridge-lambda.zip . && cd ..

# Upload to Lambda
aws lambda create-function \
  --function-name astrobridge-api \
  --runtime python3.9 \
  --role arn:aws:iam::123456789:role/lambda-exec-role \
  --handler lambda_handler.handler \
  --zip-file fileb://astrobridge-lambda.zip \
  --timeout 60 \
  --memory-size 512 \
  --environment Variables="{ASTROBRIDGE_STATE_DB=postgresql://...}"
```

---

## PyPI Release & Distribution

### Automated Release via GitHub Actions

AstroBridge includes GitHub Actions workflow for automated publishing to PyPI.

**File**: `.github/workflows/publish.yml`

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - 'v*'

jobs:
  publish:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip setuptools wheel twine
    
    - name: Build distribution
      run: |
        python setup.py sdist bdist_wheel
    
    - name: Publish to PyPI
      uses: pypa/gh-action-pypi-publish@release/v1
      with:
        password: ${{ secrets.PYPI_API_TOKEN }}
```

### Manual Release

```bash
# 1. Update version
# Edit setup.py and astrobridge/__init__.py
# Change version from 0.2.0 → 0.2.1

# 2. Commit version bump
git add setup.py astrobridge/__init__.py
git commit -m "Bump version to 0.2.1"
git push

# 3. Create git tag
git tag -a v0.2.1 -m "Release version 0.2.1"
git push origin v0.2.1

# 4. Build packages
python setup.py sdist bdist_wheel

# 5. Upload to PyPI
twine upload dist/*

# 6. Verify on PyPI
pip install astrobridge==0.2.1
```

### Version Scheme

AstroBridge follows **semantic versioning**:

- **0.2.0** → Major=0 (pre-1.0), Minor=2 (feature release), Patch=0 (bug fix)
  - 0.1.0 → 0.1.1: Patch (bug fixes)
  - 0.1.0 → 0.2.0: Minor (new features, backward compatible)
  - 0.1.0 → 1.0.0: Major (breaking changes)

---

## Production Configuration

### Environment Variables

```bash
# Core
ASTROBRIDGE_STATE_DB=postgresql://user:pass@localhost:5432/astrobridge_state
LOGLEVEL=INFO

# API
FASTAPI_ENV=production
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000
FASTAPI_WORKERS=4

# Security
ASTROBRIDGE_API_KEY=${SECURE_API_KEY}
CORS_ORIGINS=https://example.com,https://app.example.com

# Catalog Connectors
SIMBAD_TIMEOUT=30
NED_TIMEOUT=30
GAIA_TIMEOUT=60

# Monitoring
DATADOG_API_KEY=${DATADOG_KEY}
PROMETHEUS_PUSHGATEWAY=http://prometheus:9091
```

### Database Configuration

**For SQLite (Development)**:
```python
import os
from sqlalchemy import create_engine

db_path = os.getenv("ASTROBRIDGE_STATE_DB", ".astrobridge/state.db")
engine = create_engine(f"sqlite:///{db_path}")
```

**For PostgreSQL (Production)**:
```python
import os
from sqlalchemy import create_engine

db_url = os.getenv(
    "ASTROBRIDGE_STATE_DB",
    "postgresql://user:password@localhost:5432/astrobridge_state"
)
engine = create_engine(
    db_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Test connections before using
)
```

### Web Server Configuration

**Gunicorn + Uvicorn (Production)**:

```bash
# Install
pip install gunicorn uvicorn

# Run
gunicorn \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile - \
  astrobridge.web.app:app
```

**nginx Reverse Proxy**:

```nginx
upstream astrobridge {
    server localhost:8000;
    server localhost:8001;
    server localhost:8002;
    server localhost:8003;
}

server {
    listen 80;
    server_name astrobridge.example.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name astrobridge.example.com;

    ssl_certificate /etc/letsencrypt/live/astrobridge.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/astrobridge.example.com/privkey.pem;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req zone=api_limit burst=20 nodelay;

    # Logging
    access_log /var/log/nginx/astrobridge_access.log;
    error_log /var/log/nginx/astrobridge_error.log;

    location / {
        proxy_pass http://astrobridge;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

---

## Database Setup & Migration

### Initialize SQLite (Development)

```bash
# Create directory
mkdir -p .astrobridge

# Database auto-creates on first use
# Or explicitly:
python -c "
from astrobridge.jobs import JobManager
JobManager().init_db()
"
```

### Migrate to PostgreSQL (Production)

```bash
# 1. Create PostgreSQL database
createdb -U postgres astrobridge_state

# 2. Create extension for UUID support
psql -U postgres -d astrobridge_state -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"

# 3. Initialize tables (same schema works for both SQLite and PostgreSQL)
python -c "
import os
os.environ['ASTROBRIDGE_STATE_DB'] = 'postgresql://postgres@localhost/astrobridge_state'
from astrobridge.jobs import JobManager
JobManager().init_db()
"

# 4. Test connection
psql -U postgres -d astrobridge_state -c "SELECT COUNT(*) FROM jobs;"
```

### Backup & Restore

**SQLite**:
```bash
# Backup
cp .astrobridge/state.db .astrobridge/state.db.backup

# Restore
cp .astrobridge/state.db.backup .astrobridge/state.db
```

**PostgreSQL**:
```bash
# Backup
pg_dump -U postgres astrobridge_state > astrobridge_state.sql

# Restore
psql -U postgres -d astrobridge_state < astrobridge_state.sql

# Compressed backup
pg_dump -U postgres -Fc astrobridge_state > astrobridge_state.dump

# Restore from compressed
pg_restore -U postgres -d astrobridge_state astrobridge_state.dump
```

---

## Monitoring & Observability

### Application Metrics

```python
from prometheus_client import start_http_server, Counter, Histogram, Gauge
import time

# Metrics
query_counter = Counter('astrobridge_queries_total', 'Total queries', ['query_type'])
query_duration = Histogram('astrobridge_query_duration_seconds', 'Query duration')
active_queries = Gauge('astrobridge_active_queries', 'Currently running queries')
match_count = Counter('astrobridge_matches_total', 'Total matches found')

# In orchestrator
async def execute_query(request):
    active_queries.inc()
    start = time.time()
    
    try:
        response = ...
        match_count.inc(len(response.matches))
    finally:
        query_duration.observe(time.time() - start)
        active_queries.dec()
        query_counter.labels(query_type=request.query_type).inc()

# Expose metrics endpoint
start_http_server(8001)  # Prometheus scrapes http://localhost:8001/metrics
```

### Logging

```python
import logging
from pythonjsonlogger import jsonlogger

# JSON structured logging for production
logger = logging.getLogger()
handler = logging.FileHandler('/var/log/astrobridge/app.log')
formatter = jsonlogger.JsonFormatter()
handler.setFormatter(formatter)
logger.addHandler(handler)

# Logs appear as:
# {"timestamp": "2026-04-08T...", "level": "INFO", "message": "Query executed", "query_id": "..."}
```

### Health Checks

```python
from fastapi import FastAPI
from starlette.responses import JSONResponse

app = FastAPI()

@app.get("/health")
async def health():
    """Kubernetes/Docker health check."""
    return JSONResponse({"status": "healthy"}, status_code=200)

@app.get("/readiness")
async def readiness():
    """Check if service is ready for traffic."""
    try:
        # Test database connection
        from astrobridge.jobs import JobManager
        JobManager().get_summary()
        return JSONResponse({"ready": True}, status_code=200)
    except Exception as e:
        return JSONResponse(
            {"ready": False, "error": str(e)},
            status_code=503
        )
```

---

## Security & Hardening

### API Authentication

```python
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials
import os

app = FastAPI()
security = HTTPBearer()

async def verify_api_key(credentials: HTTPAuthCredentials = Depends(security)):
    """Verify API key from Authorization header."""
    valid_key = os.getenv("ASTROBRIDGE_API_KEY")
    if credentials.credentials != valid_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return credentials.credentials

@app.post("/api/jobs")
async def create_job(request: QueryRequest, token: str = Depends(verify_api_key)):
    """Protected endpoint."""
    ...
```

### CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Input Validation

```python
from pydantic import BaseModel, Field, validator

class QueryRequest(BaseModel):
    name: str = Field(..., max_length=256, min_length=1)
    search_radius_arcsec: float = Field(..., ge=0.1, le=3600)
    
    @validator('name')
    def validate_name(cls, v):
        # Prevent injection attacks
        if any(char in v for char in ['<', '>', '&', '"', "'"]):
            raise ValueError('Invalid characters in name')
        return v
```

### Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/jobs")
@limiter.limit("10/minute")
async def create_job(request: QueryRequest):
    ...
```

---

## Troubleshooting Deployments

### Container won't start

```bash
# Check logs
docker logs <container_id>

# Run with interactive shell
docker run -it astrobridge:0.2.0 /bin/bash

# Check image
docker inspect astrobridge:0.2.0
```

### Database connection issues

```bash
# Test SQLite
sqlite3 .astrobridge/state.db ".tables"

# Test PostgreSQL
psql -h localhost -U astrobridge -d astrobridge_state -c "SELECT 1;"

# Check connection string
echo $ASTROBRIDGE_STATE_DB
```

### API not responding

```bash
# Test endpoint
curl -X GET http://localhost:8000/health

# Check port binding
lsof -i :8000

# View logs
tail -f /var/log/astrobridge/app.log
```

### Memory/CPU issues

```bash
# Docker resource limits
docker run \
  --memory=1g \
  --cpus=2 \
  astrobridge:0.2.0

# Monitor resources
docker stats <container_id>

# Kubernetes limits
resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 250m
    memory: 256Mi
```

---

## Performance Tuning

### Database Query Optimization

```python
# Index frequently-queried columns
from sqlalchemy import Index

class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True)
    status = Column(String, index=True)  # Fast status lookups
    created_at = Column(DateTime, index=True)  # Time-range queries

# Create indexes
Base.metadata.create_all(engine)
```

### API Connection Pooling

```python
from sqlalchemy import create_engine

# Pool configuration for high concurrency
engine = create_engine(
    database_url,
    pool_size=20,         # Connections in pool
    max_overflow=40,      # Extra connections allowed
    pool_recycle=3600,    # Recycle connections hourly
    pool_pre_ping=True,   # Test connections before use
)
```

### Caching Layer

```python
from functools import lru_cache
from astrobridge.utilities.cache import SimpleCache

matcher_cache = SimpleCache(ttl=3600)  # 1-hour TTL

@lru_cache(maxsize=1000)
def get_source(source_id: str):
    # Cache frequent lookups
    return db.query(Source).filter_by(id=source_id).first()
```

### Async Query Optimization

```python
import asyncio

async def batch_query(coordinates: List[Tuple[float, float]]):
    """Query multiple coordinates concurrently."""
    tasks = [
        orchestrator.execute_query(QueryRequest(ra=ra, dec=dec))
        for ra, dec in coordinates
    ]
    
    # Run up to 10 concurrent queries
    results = []
    for i in range(0, len(tasks), 10):
        batch = tasks[i:i+10]
        batch_results = await asyncio.gather(*batch)
        results.extend(batch_results)
```

---

## Disaster Recovery

### Backup Strategy

```bash
# Daily automated backup
# Add to crontab: 0 2 * * * /opt/astrobridge/backup.sh

#!/bin/bash
BACKUP_DIR=/backups/astrobridge
DATE=$(date +%Y%m%d_%H%M%S)

# Backup database
pg_dump -U astrobridge astrobridge_state | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +30 -delete

# Verify backup
if [ -f $BACKUP_DIR/db_$DATE.sql.gz ]; then
    echo "Backup successful: $BACKUP_DIR/db_$DATE.sql.gz"
    # Optional: upload to S3
    aws s3 cp $BACKUP_DIR/db_$DATE.sql.gz s3://astrobridge-backups/
else
    echo "Backup failed!" | mail -s "AstroBridge Backup Alert" ops@example.com
fi
```

### Disaster Recovery Plan

**RTO (Recovery Time Objective)**: < 1 hour  
**RPO (Recovery Point Objective)**: < 4 hours (hourly backups)

```bash
# 1. Restore latest backup
gunzip < /backups/astrobridge/db_latest.sql.gz | \
  psql -U astrobridge astrobridge_state

# 2. Verify data integrity
psql -U astrobridge -d astrobridge_state -c \
  "SELECT COUNT(*) FROM jobs;"

# 3. Restart services
docker-compose restart

# 4. Verify health
curl -X GET http://localhost:8000/health
```

### High Availability

```yaml
# Kubernetes StatefulSet for HA
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: astrobridge
spec:
  serviceName: astrobridge-service
  replicas: 3
  selector:
    matchLabels:
      app: astrobridge
  template:
    metadata:
      labels:
        app: astrobridge
    spec:
      containers:
      - name: astrobridge
        image: astrobridge:0.2.0
        ports:
        - containerPort: 8000
        env:
        - name: ASTROBRIDGE_STATE_DB
          value: postgresql://....
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /readiness
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

---

## Deployment Checklist

Before deploying to production, verify:

- [ ] Version bumped in `setup.py` and `astrobridge/__init__.py`
- [ ] All tests passing: `pytest tests/ -v`
- [ ] Type checking passes: `mypy astrobridge/`
- [ ] Docker image builds: `docker build -t astrobridge:0.2.0 .`
- [ ] Environment variables documented
- [ ] Database migrations tested
- [ ] API authentication configured
- [ ] Rate limiting enabled
- [ ] Monitoring/logging configured
- [ ] Backup strategy in place
- [ ] Health checks implemented
- [ ] Git tag created: `git tag v0.2.0`
- [ ] Release notes written
- [ ] GitHub release published

---

**Last Updated**: April 8, 2026 | AstroBridge v0.2.0

For deployment support, see [docs/ARCHITECTURE_GUIDE.md](ARCHITECTURE_GUIDE.md) for integration patterns and
[docs/COMMAND_GUIDE.md](COMMAND_GUIDE.md) for CLI/API reference.
