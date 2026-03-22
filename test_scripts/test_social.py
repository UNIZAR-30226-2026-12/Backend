import requests
import uuid

BASE_URL = "http://localhost:8081"

def create_and_login(username, email, password):
    reg_data = {"username": username, "email": email, "password": password}
    requests.post(f"{BASE_URL}/api/auth/register", json=reg_data)
    login_data = {"username": username, "password": password}
    response = requests.post(f"{BASE_URL}/api/auth/login", data=login_data)
    return response.json()["access_token"]

def test_social_flow():
    # 1. Setup two users
    u1_name = f"user1_{uuid.uuid4().hex[:4]}"
    u2_name = f"user2_{uuid.uuid4().hex[:4]}"
    
    print(f"--- Setting up users: {u1_name} and {u2_name} ---")
    t1 = create_and_login(u1_name, f"{u1_name}@test.com", "pass123")
    t2 = create_and_login(u2_name, f"{u2_name}@test.com", "pass123")
    
    h1 = {"Authorization": f"Bearer {t1}"}
    h2 = {"Authorization": f"Bearer {t2}"}

    # 2. User 1 sends request to User 2
    print(f"\n--- {u1_name} sending friend request to {u2_name} ---")
    response = requests.post(f"{BASE_URL}/api/friends/request", json={"username": u2_name}, headers=h1)
    print(f"Response: {response.json()}")

    # 3. User 2 lists friends/requests
    print(f"\n--- {u2_name} listing friends and requests ---")
    response = requests.get(f"{BASE_URL}/api/friends", headers=h2)
    data = response.json()
    print(f"Pending requests for User 2: {data['requests']}")
    
    u1_id = data['requests'][0]['id'] if data['requests'] else None
    if not u1_id:
        print("Error: Request not found")
        return

    # 4. User 2 accepts request
    print(f"\n--- {u2_name} accepting request from {u1_name} (ID: {u1_id}) ---")
    response = requests.post(f"{BASE_URL}/api/friends/{u1_id}/accept", headers=h2)
    print(f"Response: {response.json()}")

    # 5. List friends again
    print("\n--- Verifying friendship ---")
    response = requests.get(f"{BASE_URL}/api/friends", headers=h1)
    print(f"{u1_name} friends: {response.json()['friends']}")

    # 6. Delete friend
    print(f"\n--- {u1_name} deleting {u2_name} ---")
    # Need user 2 ID. We can get it from the profile
    u2_id = requests.get(f"{BASE_URL}/api/users/me", headers=h2).json()["id"]
    response = requests.delete(f"{BASE_URL}/api/friends/{u2_id}", headers=h1)
    print(f"Response: {response.json()}")

if __name__ == "__main__":
    test_social_flow()
