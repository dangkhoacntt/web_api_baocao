import requests

url = 'http://localhost:5000/api/v1/resource'
headers = {
    'API-Key': 'be8f1f561032cd721d9ecd8884aacc4e',
    'Content-Type': 'application/json'
}
data = {
    'success': True
}

response = requests.post(url, headers=headers, json=data)

print(response.status_code)
print(response.json())
