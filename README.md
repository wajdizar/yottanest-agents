# YottaNest Agents

An AI-powered compliance report generation platform built on DeerFlow.

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](./backend/pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)](./writing-service/requirements.txt)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

## Overview

YottaNest Agents extends [DeerFlow](https://github.com/bytedance/deer-flow) (v2.0-m1-rc1) with a specialized **Writing Service** for generating structured compliance reports. The platform combines DeerFlow's powerful agent harness with custom report generation capabilities.

## Architecture

```
yottanest-agents/
├── backend/                 # DeerFlow backend (agent harness)
├── frontend/                # DeerFlow frontend (web UI)
├── writing-service/         # Report generation microservice (NEW)
│   ├── app/
│   │   ├── agents/          # 8 LangChain agents
│   │   ├── endpoints/       # REST/SSE API endpoints
│   │   ├── schemas/         # Pydantic v2 data contracts
│   │   └── harness/         # DeerFlow integration
│   └── tests/               # 61 passing tests
└── config.yaml              # Shared configuration
```

## Writing Service

The Writing Service is a FastAPI microservice for generating structured compliance reports (KYC profiles, due diligence, regulatory assessments).

### Features

- **6 API Endpoints**: Plan, retrieve, write, revise, consistency check
- **8 LangChain Agents**: Structure builder, retrieval planner, section writer, and more
- **Parallel Processing**: Concurrent section writing with retry/timeout
- **DeerFlow Integration**: Uses shared model factory and configuration
- **SSE Streaming**: Real-time progress updates for long-running operations
- **Full Test Coverage**: 61 passing tests

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/report-writer/plan` | POST | Generate report structure from goal |
| `/api/report-writer/retrieve/plan` | POST | Plan evidence retrieval queries |
| `/api/report-writer/retrieve/evaluate` | POST | Evaluate evidence coverage |
| `/api/report-writer/write` | POST (SSE) | Write report sections in parallel |
| `/api/report-writer/revise` | POST (SSE) | Revise sections based on feedback |
| `/api/report-writer/consistency` | POST | Check report consistency |

### Model Configuration

The Writing Service uses three model tiers configured in `config.yaml`:

```yaml
writing_service:
  model_heavy: ollama-yi-34b      # Planning, assembly, consistency
  model_standard: ollama-qwen2.5  # Section writing
  model_light: ollama-qwen2.5     # Editing, checking
  write_timeout: 600
  section_timeout: 120
```

### Running the Writing Service

```bash
cd writing-service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e ../backend/packages/harness  # DeerFlow integration

uvicorn app.main:app --host 0.0.0.0 --port 8500
```

### Health Check

```bash
curl http://localhost:8500/health
```

```json
{
  "status": "healthy",
  "service": "writing-service",
  "integration": "deerflow",
  "models_available": 3,
  "config": {
    "model_heavy": "ollama-yi-34b",
    "model_standard": "ollama-qwen2.5",
    "model_light": "ollama-qwen2.5"
  }
}
```

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 22+
- Docker (recommended)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/wajdizar/yottanest-agents.git
   cd yottanest-agents
   ```

2. **Configure models**
   ```bash
   cp config.example.yaml config.yaml
   # Edit config.yaml with your LLM provider settings
   ```

3. **Start DeerFlow**
   ```bash
   make setup
   make dev
   ```
   Access: http://localhost:2026

4. **Start Writing Service**
   ```bash
   cd writing-service
   source venv/bin/activate
   uvicorn app.main:app --port 8500
   ```
   Access: http://localhost:8500

## Testing

```bash
cd writing-service
source venv/bin/activate
pytest -v
```

```
======================== 61 passed, 1 skipped =========================
```

## Based On

This project is built on [DeerFlow v2.0-m1-rc1](https://github.com/bytedance/deer-flow) by ByteDance.

DeerFlow is a super agent harness that orchestrates sub-agents, memory, and sandboxes — powered by extensible skills. See the [DeerFlow documentation](https://github.com/bytedance/deer-flow) for full platform capabilities.

## License

This project is open source under the [MIT License](./LICENSE).

## Acknowledgments

- [DeerFlow](https://github.com/bytedance/deer-flow) by ByteDance - The agent harness foundation
- [LangChain](https://github.com/langchain-ai/langchain) - LLM framework
- [LangGraph](https://github.com/langchain-ai/langgraph) - Multi-agent orchestration
