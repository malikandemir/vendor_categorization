# GitHub Actions Setup Guide

This document explains how to set up GitHub Actions for the Finance Vendor Categorization Tool.

## Workflow Overview

The GitHub Actions workflow (`python-app.yml`) automates testing and deployment of the application. It consists of two main jobs:

1. **python-tests**: Runs tests on the Python Flask application
2. **deploy**: Deploys the application to your server via SSH

## Required GitHub Secrets

To use this workflow, you need to set up the following secrets in your GitHub repository:

1. **SSH_HOST**: The hostname or IP address of your server
2. **SSH_USER**: The username to use when connecting to your server
3. **SSH_PRIVATE_KEY**: The SSH private key for authentication
4. **SSH_PORT**: The SSH port (usually 22)
5. **SSH_PASSPHRASE**: The passphrase for your SSH key (if applicable)

## Setting Up GitHub Secrets

1. Go to your GitHub repository
2. Click on "Settings" > "Secrets and variables" > "Actions"
3. Click "New repository secret"
4. Add each of the required secrets listed above

## Workflow File Location

The workflow file is located at:
```
.github/workflows/python-app.yml
```

## Customizing the Workflow

You may need to customize the workflow based on your specific requirements:

- **Python Version**: Currently set to 3.9, change if needed
- **Branch Name**: Currently set to trigger on pushes to `main`
- **Deployment Path**: Currently set to `/home/malikan2/vendor_categorization`
- **Test Commands**: Add your specific test commands in the "Run tests" step

## Troubleshooting

If you encounter the error `cp: cannot stat 'vendor_categorization/.env.example': No such file or directory`, make sure:

1. Your `.env.example` file exists in the vendor_categorization directory
2. The file paths in the workflow match your actual project structure
