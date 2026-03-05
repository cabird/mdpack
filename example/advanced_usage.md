Title: Advanced Usage
Description: Power-user features and customisation options
Prereqs: Getting Started, Setup Guide

# Advanced Usage

This guide covers advanced features. Make sure you've read the
prerequisite guides first.

## Binary Files

Binary files (images, documents, etc.) can be included in bundles.
They are base64-encoded during packing and decoded during unpacking.

Specify them in `manifest.toml`:

```toml
binary_files = ["assets/logo.png", "reports/*.pdf"]
```

