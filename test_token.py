import requests

url = "https://test.api.amadeus.com/v1/security/oauth2/token"

data = {
    "grant_type": "client_credentials",
    "client_id": "0XGGUO9oPzn0WVAZBjTBGjgFXb5KnKs4",
    "client_secret": "l9RP4AnpciYNJ8AS"
}

headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}

response = requests.post(url, data=data, headers=headers)

print(response.status_code)
print(response.text)