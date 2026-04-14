# RecoveryIntelligenceSystem
# Medical A2A Workflow

This project builds a multi-agent clinical + insurance reasoning workflow.

## Components
- Clinical Agent: reads patient summary, PT notes, and imaging, then returns structured clinical reasoning
- Insurance Agent: retrieves relevant policy clauses and returns structured coverage reasoning
- Orchestrator: merges agent outputs, detects conflicts, and generates an executable workflow
- Prompt Opinion: frontend/demo layer for chat interaction and presentation

## Current Goal
Build a minimal end-to-end demo where:
1. user asks a care question
2. backend agent system returns structured JSON
3. Prompt Opinion renders the result into a user-friendly answer
