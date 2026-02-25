# Agentic Travel Assistant (LangGraph + FastAPI)

An agentic backend travel assistant that understands natural-language
travel queries, decides which tools to call (flight search and hotel
search), retrieves real-world data, and synthesizes a structured,
user-friendly response.

## Features

-   Natural language travel query understanding
-   Flight and hotel search tools
-   FastAPI endpoint
-   LangGraph orchestration
-   Cloud or local LLM support

## Installation

### Clone repository

git clone https://github.com/YOUR_USERNAME/agentic-travel-assistant.git
cd agentic-travel-assistant

### Create virtual environment

python -m venv venv venv`\Scripts`{=tex}`\activate`{=tex}

### Install dependencies

pip install -r requirements.txt

## Environment setup

Create .env file:

LLM_PROVIDER=openai OPENAI_API_KEY=your_key_here

TRAVEL_API_KEY=your_key_here TRAVEL_API_SECRET=your_secret_here

## Run server

uvicorn src.main:app --reload --port 8000

## API usage

POST /query

{ "user_id": "user1", "query": "Flight from BOM to DEL on 2026-05-30" }

## Run tests

pytest

## Documentation

See docs/architecture.md
