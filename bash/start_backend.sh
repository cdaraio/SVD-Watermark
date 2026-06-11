#!/bin/bash
cd "$(dirname "$0")/.."
uvicorn main:app --reload