.PHONY: help setup check-prereqs build build-dev deploy deploy-dev clean status logs unmount-dev

# Variables
PROJECT_ROOT := $(shell pwd)
ANCHOR_WEB_DIR := $(PROJECT_ROOT)/anchor_web
CONFIGMAP_NAME := web-app-env-dev
MOUNT_PID_FILE := .minikube-mount.pid

# Default target
help:
	@echo "Anchor Project - Makefile Commands"
	@echo ""
	@echo "Setup & Configuration:"
	@echo "  make setup          - Setup minikube (check prerequisites, start minikube, enable addons)"
	@echo "  make check-prereqs  - Check if Docker, minikube, and kubectl are installed"
	@echo ""
	@echo "Build:"
	@echo "  make build          - Build production Docker images (Python + Next.js)"
	@echo "  make build-dev      - Build development Docker image (Next.js only)"
	@echo ""
	@echo "Deploy:"
	@echo "  make deploy         - Deploy production application to minikube"
	@echo "  make deploy-dev     - Deploy development environment with hot-reloading"
	@echo ""
	@echo "Development:"
	@echo "  make status         - Show Kubernetes services and pods"
	@echo "  make logs           - Show logs from web-app pod"
	@echo "  make unmount-dev    - Stop minikube mount for hot-reloading"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          - Delete all Kubernetes resources"
	@echo ""

# Check prerequisites
check-prereqs:
	@echo "Checking prerequisites..."
	@command -v docker >/dev/null 2>&1 || { \
		echo "Error: Docker is not installed."; \
		echo "  macOS: brew install --cask docker"; \
		echo "  Linux: See https://docs.docker.com/engine/install/"; \
		exit 1; \
	}
	@docker info >/dev/null 2>&1 || { \
		echo "Error: Docker daemon is not running."; \
		echo "Please start Docker Desktop and ensure it's running."; \
		exit 1; \
	}
	@echo "✓ Docker is installed and running"
	@command -v minikube >/dev/null 2>&1 || { \
		echo "Error: minikube is not installed."; \
		echo "  macOS: brew install minikube"; \
		echo "  Linux: See https://minikube.sigs.k8s.io/docs/start/"; \
		exit 1; \
	}
	@command -v kubectl >/dev/null 2>&1 || { \
		echo "Error: kubectl is not installed."; \
		echo "  macOS: brew install kubectl"; \
		echo "  Linux: See https://kubernetes.io/docs/tasks/tools/"; \
		exit 1; \
	}
	@echo "✓ All prerequisites are installed"

# Setup minikube
setup: check-prereqs
	@echo "Setting up minikube..."
	@if ! minikube status >/dev/null 2>&1; then \
		echo "Starting minikube..."; \
		minikube start --memory=4096 --cpus=2; \
	else \
		echo "✓ Minikube is already running"; \
	fi
	@echo "Enabling minikube addons..."
	@minikube addons enable ingress >/dev/null 2>&1 || true
	@echo "✓ Minikube setup complete!"

# Build production images
build: setup
	@echo "Building Docker images for minikube..."
	@eval $$(minikube docker-env) && \
		echo "Building Python FastAPI image..." && \
		docker build -f Dockerfile.python -t stock-analysis-agent:latest . && \
		echo "Building Next.js web app image..." && \
		docker build -f Dockerfile.nodejs -t web-app:latest .
	@echo "✓ Images built successfully!"

# Build development image
build-dev: setup
	@echo "Building development Docker image..."
	@eval $$(minikube docker-env) && \
		docker build -f Dockerfile.nodejs.dev -t web-app:dev .
	@echo "✓ Development image built successfully!"

# Deploy production application
deploy: build
	@echo "Deploying application to minikube..."
	@echo "Applying secrets (if web-app-secrets.yaml exists)..."
	@kubectl apply -f k8s/prod/web-app-secrets.yaml 2>/dev/null || echo "  Note: web-app-secrets.yaml not found or already applied. Create it with your production secrets."
	@kubectl apply -f k8s/prod/stock-analysis-agent-deployment.yaml
	@kubectl apply -f k8s/prod/web-app-deployment.yaml
	@echo "Waiting for deployments to be ready..."
	@kubectl wait --for=condition=available --timeout=300s deployment/stock-analysis-agent || true
	@kubectl wait --for=condition=available --timeout=300s deployment/web-app || true
	@echo ""
	@echo "✓ Deployment complete!"
	@echo ""
	@$(MAKE) status
	@echo ""
	@echo "Access the web app at: http://$$(minikube ip):30080"
	@echo "Or use port forwarding: kubectl port-forward service/web-app 3000:3000"

# Deploy development environment
deploy-dev: build-dev
	@echo "Setting up minikube mount for hot-reloading..."
	@if [ ! -d "$(ANCHOR_WEB_DIR)/src" ]; then \
		echo "Error: anchor_web/src directory not found at $(ANCHOR_WEB_DIR)/src"; \
		exit 1; \
	fi
	@if [ -f "$(MOUNT_PID_FILE)" ]; then \
		PID=$$(cat $(MOUNT_PID_FILE)); \
		if ps -p $$PID > /dev/null 2>&1; then \
			echo "Minikube mount is already running (PID: $$PID)"; \
		else \
			rm $(MOUNT_PID_FILE); \
			echo "Starting minikube mount..."; \
			minikube mount "$(ANCHOR_WEB_DIR)/src:/mnt/anchor-web/src" >/dev/null 2>&1 & \
			echo $$! > $(MOUNT_PID_FILE); \
			sleep 2; \
			echo "✓ Minikube mount started (PID: $$(cat $(MOUNT_PID_FILE)))"; \
		fi; \
	else \
		echo "Starting minikube mount..."; \
		minikube mount "$(ANCHOR_WEB_DIR)/src:/mnt/anchor-web/src" >/dev/null 2>&1 & \
		echo $$! > $(MOUNT_PID_FILE); \
		sleep 2; \
		echo "✓ Minikube mount started (PID: $$(cat $(MOUNT_PID_FILE)))"; \
	fi
	@echo ""
	@echo "Applying development deployment..."
	@kubectl apply -f k8s/dev/web-app-configmap.yaml
	@kubectl apply -f k8s/dev/web-app-deployment.dev.yaml
	@echo "Waiting for deployment to be ready..."
	@kubectl wait --for=condition=available --timeout=300s deployment/web-app || true
	@echo ""
	@echo "✓ Development environment is ready!"
	@echo ""
	@$(MAKE) status
	@echo ""
	@echo "Access the web app at: http://$$(minikube ip):30080"
	@echo "Or use port forwarding: kubectl port-forward service/web-app 3000:3000"
	@echo ""
	@if [ -f "$(MOUNT_PID_FILE)" ]; then \
		echo "Minikube mount is running (PID: $$(cat $(MOUNT_PID_FILE)))"; \
		echo "To stop the mount, run: make unmount-dev"; \
		echo ""; \
	fi
	@echo "Note: Changes to files in anchor_web/src/ will be reflected immediately!"

# Show Kubernetes status
status:
	@echo "Services:"
	@kubectl get services
	@echo ""
	@echo "Pods:"
	@kubectl get pods

# Show logs from web-app pod
logs:
	@POD=$$(kubectl get pods -l app=web-app -o jsonpath='{.items[0].metadata.name}' 2>/dev/null); \
	if [ -z "$$POD" ]; then \
		echo "No web-app pod found"; \
	else \
		kubectl logs -f $$POD; \
	fi

# Stop minikube mount
unmount-dev:
	@if [ -f "$(MOUNT_PID_FILE)" ]; then \
		PID=$$(cat $(MOUNT_PID_FILE)); \
		if ps -p $$PID > /dev/null 2>&1; then \
			kill $$PID && \
			rm $(MOUNT_PID_FILE) && \
			echo "✓ Minikube mount stopped"; \
		else \
			rm $(MOUNT_PID_FILE) && \
			echo "Minikube mount was not running"; \
		fi; \
	else \
		echo "No mount PID file found. Mount may not be running."; \
	fi

# Cleanup Kubernetes resources
clean: unmount-dev
	@echo "Cleaning up Kubernetes resources..."
	@kubectl delete -f k8s/ 2>/dev/null || true
	@echo "✓ Cleanup complete!"
	@echo ""
	@echo "To remove minikube entirely: minikube delete"
