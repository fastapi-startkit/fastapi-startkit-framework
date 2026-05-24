# Agent Memory System

## Goals

Build a production-grade memory system for AI agents that supports:

- semantic memory
- episodic memory
- task memory
- retrieval ranking
- memory consolidation
- reflection
- decay/forgetting

---

# Architecture

## Components

### 1. Memory Router

Responsible for:
- classifying memory
- routing to correct store
- embedding generation
- deduplication

---

### 2. Semantic Memory

Stores:
- user preferences
- knowledge
- facts
- long-term summaries

Storage:
- PostgreSQL
- pgvector

Features:
- embedding search
- hybrid retrieval
- deduplication
- confidence scoring

---

### 3. Episodic Memory

Stores:
- actions
- events
- failures
- tool outputs
- timelines

Storage:
- append-only PostgreSQL table

Features:
- chronological retrieval
- summarization
- temporal filtering

---

### 4. Task Memory

Stores:
- objectives
- todos
- completed steps
- agent progress

Storage:
- structured relational tables

Features:
- task lifecycle
- dependencies
- state transitions

---

### 5. Retrieval Layer

Supports:
- semantic search
- keyword search
- recency ranking
- importance ranking

Retrieval score formula:

score =
    similarity
    + recency
    + importance
    + task relevance
    + confidence

---

### 6. Reflection Engine

Responsible for:
- summarization
- extracting patterns
- converting episodes into semantic knowledge

Example:
Repeated deployment failures
→ deployment validation checklist

---

### 7. Memory Decay

Supports:
- TTL
- archival
- confidence decay
- stale memory cleanup

---

# Database Tables

## semantic_memories

- id
- content
- embedding
- confidence
- created_at
- updated_at

## episodic_events

- id
- event_type
- content
- outcome
- timestamp

## tasks

- id
- title
- status
- created_at
- updated_at

## task_steps

- id
- task_id
- step
- status

---

# Fluent API

```python
memory.capture(...)

memory.search(...)

memory.semantic.add(...)

memory.tasks.create(...)

memory.reflect()
