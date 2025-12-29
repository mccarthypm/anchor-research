# Anchor - Stock Analysis Application

A stock analysis application with a Next.js web frontend and a Python FastAPI backend.

## Kubernetes Deployment with Minikube

This application can be deployed to minikube for local development and testing.

### Quick Start

1. **Setup minikube** (first time only):
   ```bash
   ./scripts/setup-minikube.sh
   ```

2. **Build Docker images**:
   ```bash
   ./scripts/build-images.sh
   ```

3. **Deploy to Kubernetes**:
   ```bash
   ./scripts/deploy.sh
   ```

4. **Access the application**:
   - Web app: http://localhost:30080
   - Or use: `minikube service web-app`
   - Or port forward: `kubectl port-forward service/web-app 3000:3000`

For detailed instructions, see [k8s/README.md](k8s/README.md) and [k8s/README-ENV.md](k8s/README-ENV.md).

## Architecture

- **Web App** (Next.js): Frontend web application
- **Stock Analysis Agent** (FastAPI): Backend API for analyzing SEC filings

## Development

### Python Backend

```bash
# Navigate to backend directory
cd anchor_backend

# Install dependencies
uv sync

# Run the FastAPI server
uv run python -m uvicorn agents.stock_analysis.server:app --reload
```

### Next.js Frontend

```bash
cd anchor_web
npm install
npm run dev
```

## Docker Images

- `Dockerfile.python`: Python FastAPI server
- `Dockerfile.nodejs`: Next.js web application

