# Azure OpenAI Troubleshooting Guide

This document is a detailed guide on troubleshooting common issues that occur when switching to a new Azure OpenAI model deployment or updating API credentials in the `.env` file. 

If you or an AI assistant encounter repeated `Connection error` or `404 Resource not found` issues despite updating the `.env` file, **read this guide first.**

---

## 1. Stale Environment Variables in the Terminal (The "Phantom Cache" Issue)

**Symptoms:**
- You update the `.env` file with new credentials, but the script still throws a `404 Resource not found` or `Connection error`.
- Tests prove the credentials in `.env` are correct, but running the script locally continues to fail.

**Root Cause:**
The Python script uses `python-dotenv` (`load_dotenv()`) to load variables from the `.env` file. By design, **`load_dotenv()` does NOT override existing environment variables that are already set in your terminal session.**
If you previously ran `source .env` or manually exported variables (e.g., `export APP_AZURE_OPENAI_ENDPOINT=...`), those old, invalid credentials remain in your terminal's memory. The script will quietly use the old broken endpoint instead of the new one in the `.env` file.

**How to Fix:**
1. **Quick Fix:** Unset the cached variables before running the script:
   ```bash
   unset APP_AZURE_OPENAI_API_KEY APP_AZURE_OPENAI_ENDPOINT APP_AZURE_OPENAI_DEPLOYMENT APP_AZURE_OPENAI_API_VERSION
   ```
2. **Best Practice:** Close your terminal and open a brand new one. Do not run `source .env` before running the Python script. Let `load_dotenv()` do its job naturally.

---

## 2. Incorrect Endpoint URL Formatting (The 404 Error)

**Symptoms:**
- Error message: `⚠ Azure API error: Error code: 404 - {'error': {'code': '404', 'message': 'Resource not found'}}`

**Root Cause:**
When copying the endpoint from the Azure AI portal, it might look something like this:
`https://<resource-name>.services.ai.azure.com/openai/v1/responses`

If you paste this exact string into your `.env` file, it will fail. The Azure Python SDK automatically appends its own routing paths (like `/openai/deployments/<deployment_name>/chat/completions`) to the endpoint you provide.
If you provide a URL that already has a path, the SDK creates a mashed, invalid URL (e.g., `.../openai/v1/responses/openai/deployments/...`), which Azure rejects with a 404.

**How to Fix:**
Your `.env` file must contain **only the base URL**, with no trailing slashes or paths.

❌ **Incorrect:** 
`APP_AZURE_OPENAI_ENDPOINT=https://my-resource.services.ai.azure.com/openai/v1/responses`

✅ **Correct:** 
`APP_AZURE_OPENAI_ENDPOINT=https://my-resource.services.ai.azure.com`

---

## 3. The `export` Prefix in the `.env` File

**Symptoms:**
- Network connection failures or parsing errors when reading variables.

**Root Cause:**
While it might be tempting to write `.env` files like a bash script using `export KEY=VALUE`, this is not standard for `.env` files. Depending on the version of `python-dotenv` or how the variables are parsed, the word `export ` might accidentally be included as part of the URL (e.g., the URL literally becomes `export https://...`), which immediately breaks HTTP requests and results in a `Connection error`.

**How to Fix:**
Always use plain `KEY=VALUE` pairs without the `export` command.

❌ **Incorrect:**
```env
export APP_AZURE_OPENAI_API_KEY=my-key
export APP_AZURE_OPENAI_ENDPOINT=https://my-resource.services.ai.azure.com
```

✅ **Correct:**
```env
APP_AZURE_OPENAI_API_KEY=my-key
APP_AZURE_OPENAI_ENDPOINT=https://my-resource.services.ai.azure.com
```

---

## Quick Checklist for Future AI Assistants

If the user reports Azure API errors after deploying a new model:
1. **Check the Endpoint Format:** Ensure `APP_AZURE_OPENAI_ENDPOINT` in `.env` is just the base URL (no `/openai/...` paths).
2. **Check for `export`:** Ensure there are no `export ` prefixes in the `.env` file.
3. **Clear Terminal Cache:** Instruct the user to restart their terminal or run `unset` on the relevant environment variables to clear old cached credentials, as `load_dotenv()` will silently ignore the `.env` file if terminal variables are already set.
