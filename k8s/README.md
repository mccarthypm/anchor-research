# Installation Guide

This guide will help you install all prerequisites for running the Anchor application with minikube.

## Prerequisites

1. **Docker** - Container runtime
2. **minikube** - Local Kubernetes cluster
3. **kubectl** - Kubernetes command-line tool

## Installation Steps

### 1. Install Docker
1. Download Docker Desktop from: https://www.docker.com/products/docker-desktop/
2. Install the `.dmg` file
3. Launch Docker Desktop from Applications
4. Wait for Docker to start (whale icon in menu bar)

### 2. Install minikube
```bash
brew install minikube
```

#### Verify Installation
```bash
minikube version
```

### 3. Install kubectl
```bash
brew install kubectl
```

#### Verify Installation
```bash
kubectl version --client
```

## Quick Start

### Using Makefile (Recommended)

```bash
# See all available commands
make help

# Development
make deploy-dev    # Setup and deploy development environment with hot-reloading

# Production
make deploy        # Build images and deploy production environment
```

## Manual Deployment

### Development
```bash
kubectl apply -f k8s/dev/
```

### Production
```bash
kubectl apply -f k8s/prod/
```

## Cleanup

```bash
make clean
```

Or manually:
```bash
kubectl delete -f k8s/dev/
kubectl delete -f k8s/prod/
```
