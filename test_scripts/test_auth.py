import requests
import uuid

BASE_URL = "http://localhost:8081"

def test_auth_flow():
    # 1. Register a new user
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "password123"
    
    print(f"--- 1. Testing Registration for {username} ---")
    reg_data = {
        "username": username,
        "email": email,
        "password": password
    }
    
    response = requests.post(f"{BASE_URL}/api/auth/register", json=reg_data)
    if response.status_code == 200:
        print("Registration successful!")
        user_data = response.json()
        print(f"User ID: {user_data['id']}")
    else:
        print(f"Registration failed: {response.status_code} - {response.text}")
        return

    # 2. Login
    print("\n--- 2. Testing Login ---")
    login_data = {
        "username": username,
        "password": password
    }
    # OAuth2PasswordRequestForm expects form data, not JSON
    response = requests.post(f"{BASE_URL}/api/auth/login", data=login_data)
    if response.status_code == 200:
        token_data = response.json()
        token = token_data["access_token"]
        print("Login successful!")
        print(f"Token: {token[:20]}...")
    else:
        print(f"Login failed: {response.status_code} - {response.text}")
        return

    # 3. Get Me
    print("\n--- 3. Testing GET /api/users/me ---")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/users/me", headers=headers)
    if response.status_code == 200:
        print("Get Me successful!")
        print(response.json())
    else:
        print(f"Get Me failed: {response.status_code} - {response.text}")

    # 4. Update Profile
    print("\n--- 4. Testing PUT /api/users/me ---")
    update_data = {
        "email": f"updated_{email}"
    }
    response = requests.put(f"{BASE_URL}/api/users/me", json=update_data, headers=headers)
    if response.status_code == 200:
        print("Update profile successful!")
        print(response.json())
    else:
        print(f"Update profile failed: {response.status_code} - {response.text}")

    # 5. Get User Stats
    user_id = user_data['id']
    print(f"\n--- 5. Testing GET /api/users/{user_id}/stats ---")
    response = requests.get(f"{BASE_URL}/api/users/{user_id}/stats")
    if response.status_code == 200:
        print("Get stats successful!")
        print(response.json())
    else:
        print(f"Get stats failed: {response.status_code} - {response.text}")

if __name__ == "__main__":
    test_auth_flow()
