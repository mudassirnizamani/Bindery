"""
Azure OpenAI API Client
Encapsulates logic for interacting with Azure OpenAI models.
"""

import os
import time
from openai import AzureOpenAI, RateLimitError, APIError, BadRequestError

class AzureClient:
    def __init__(self):
        self.api_key = os.getenv('APP_AZURE_OPENAI_API_KEY')
        endpoint = os.getenv('APP_AZURE_OPENAI_ENDPOINT')
        self.deployment = os.getenv('APP_AZURE_OPENAI_DEPLOYMENT')
        self.api_version = os.getenv('APP_AZURE_OPENAI_API_VERSION')

        if not all([self.api_key, endpoint, self.deployment, self.api_version]):
             missing = []
             if not self.api_key: missing.append('APP_AZURE_OPENAI_API_KEY')
             if not endpoint: missing.append('APP_AZURE_OPENAI_ENDPOINT')
             if not self.deployment: missing.append('APP_AZURE_OPENAI_DEPLOYMENT')
             if not self.api_version: missing.append('APP_AZURE_OPENAI_API_VERSION')
             raise ValueError(f"Missing Azure OpenAI environment variables: {', '.join(missing)}")

        # Clean endpoint if it contains the full path
        # If user provides: https://.../openai/deployments/...
        # We need: https://.../
        if "openai/deployments" in endpoint:
            self.endpoint = endpoint.split("/openai/deployments")[0]
            if not self.endpoint.endswith('/'):
                self.endpoint += '/'
        else:
            self.endpoint = endpoint

        try:
            self.client = AzureOpenAI(
                api_key=self.api_key,
                api_version=self.api_version,
                azure_endpoint=self.endpoint,
                azure_deployment=self.deployment
            )
            print(f"✓ Azure OpenAI initialized (Deployment: {self.deployment})")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Azure OpenAI client: {e}")

    def generate_content(self, prompt: str, max_retries: int = 5) -> str:
        """Call Azure OpenAI with retry logic"""
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment, # In Azure SDK, model often acts as deployment name too, but client is configured with azure_deployment
                    messages=[
                        {"role": "system", "content": "You are a professional book editor."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1, # Low temperature for consistent cleaning
                )

                # Log usage and finish reason
                usage = response.usage
                finish_reason = response.choices[0].finish_reason
                # print(f"    ℹ Token Usage: Prompt={usage.prompt_tokens}, Completion={usage.completion_tokens}, Total={usage.total_tokens} | Finish Reason: {finish_reason}")

                # Check for content filter immediately
                if finish_reason == 'content_filter':
                    print("    ⚠ Azure Content Filter triggered (finish_reason).")
                    return None

                content = response.choices[0].message.content
                if content is None:
                    return "" # Return empty string if just empty content

                return content.strip()
            except RateLimitError:
                 if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"    ⏳ Rate limit hit. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
            except BadRequestError as e:
                # Check for content filter
                if e.body and isinstance(e.body, dict):
                    error_details = e.body.get('error', {})
                    if error_details.get('code') == 'content_filter':
                        print(f"    ⚠ Azure Content Filter triggered: {error_details.get('message')}")
                        return None # Fail immediately, do not retry

                print(f"    ⚠ Azure Bad Request error: {e}")
                time.sleep(2)
            except APIError as e:
                print(f"    ⚠ Azure API error: {e}")
                time.sleep(2)
            except Exception as e:
                print(f"    ⚠ Azure call failed: {e}")
                time.sleep(2)

        return None
