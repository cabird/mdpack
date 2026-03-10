---
title: Setup Guide
description: Environment and configuration setup instructions
---

# Setup Guide

This document covers environment setup and configuration.

## Python Environment

Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

## Configuration

The project uses `manifest.toml` for all configuration. See the README
for a full reference of available options.

## Verification

Run the self-test to verify everything works:

```bash
python self_test.py
```
