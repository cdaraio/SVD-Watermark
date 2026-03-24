#!/bin/bash

# root del progetto
cd "$(dirname "$0")/.."

# Entra nella cartella frontend
cd frontend

echo "Avvio frontend..."
npm install
npm run dev