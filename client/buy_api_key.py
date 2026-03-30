import os
import sys
import time
import requests
import webbrowser

# Adjust this to match your actual deployed Cloud Run/Gateway URL
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

def main():
    print("="*60)
    print(" Welcome to the Synthetic Market Data Setup Utility ")
    print("="*60)
    print("Generating a secure Stripe Checkout Session...")

    # 1. Request a new checkout session
    try:
        response = requests.post(f"{API_BASE_URL}/checkout")
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] Failed to contact the backend to start checkout: {e}")
        sys.exit(1)

    checkout_url = data.get("checkout_url")
    session_id = data.get("session_id")

    if not checkout_url or not session_id:
        print("\n[ERROR] Invalid response from backend.")
        sys.exit(1)

    # 2. Direct the user to the secure payment portal
    print("\nTo securely purchase your API Key, please complete your payment via Stripe.")
    print("Opening your browser...")
    time.sleep(1)

    try:
        webbrowser.open(checkout_url)
    except Exception:
        pass # Silently fail if browser can't be opened

    print(f"\nIf your browser didn't open automatically, click here: \n-> {checkout_url}\n")
    print("Waiting for payment confirmation. Do not close this terminal...")

    # 3. Poll the backend until the webhook completes and the API key is provisioned
    max_retries = 100 # Approx 5 minutes at 3s intervals
    for _ in range(max_retries):
        try:
            status_response = requests.get(f"{API_BASE_URL}/status/{session_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                status = status_data.get("status")

                if status == "completed":
                    api_key = status_data.get("api_key")
                    print("\n" + "="*60)
                    print("[SUCCESS] Payment confirmed! Your API key has been provisioned.")
                    print("="*60)
                    print(f"Your API Key: {api_key}")
                    print("\nSaving key to local .env file...")

                    with open(".env", "a") as f:
                        f.write(f"\nSYNTHETIC_API_KEY={api_key}\n")

                    print("Done. You are ready to start using the Synthetic Data API.")
                    sys.exit(0)
                elif status == "failed":
                    print("\n[ERROR] The payment or API key provisioning failed.")
                    sys.exit(1)
        except requests.exceptions.RequestException:
            pass # Ignore intermittent connection errors while polling

        sys.stdout.write(".")
        sys.stdout.flush()
        time.sleep(3)

    print("\n[ERROR] Polling timed out. If you completed payment, please contact support.")
    sys.exit(1)

if __name__ == "__main__":
    main()
