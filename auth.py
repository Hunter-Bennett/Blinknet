from fastapi import Form, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi_login import LoginManager
import json
import os

# --- Login manager ---
SECRET = "supersecretkey"
manager = LoginManager(SECRET, token_url="/login", use_cookie=True)
manager.cookie_name = "access-token"

# File path for users
USERS_FILE = "users.json"

# Load users from file
def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"admin": {"username": "admin", "password": "admin123"}}
    return {"admin": {"username": "admin", "password": "admin123"}}

# Save users to file
def save_users():
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

# --- In-memory users (loaded from file) ---
users = load_users()

# --- User loader for fastapi-login ---
@manager.user_loader()
def load_user(username: str):
    user = users.get(username)
    return user

# --- Routes for login/logout ---
def login_routes(app, templates):
    @app.get("/login")
    async def login_get(request: Request):
        return templates.TemplateResponse("login.html", {"request": request, "error": None})

    @app.post("/login")
    async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
        user = users.get(username)
        if not user or password != user["password"]:
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"}, status_code=401)
        
        access_token = manager.create_access_token(data={"sub": username})
        response = RedirectResponse("/", status_code=303)
        manager.set_cookie(response, access_token)
        return response

    @app.get("/logout")
    async def logout():
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(key=manager.cookie_name)
        return response
    
    @app.get("/change-password")
    async def change_password_get(request: Request, user=Depends(manager)):
        return templates.TemplateResponse("change_password.html", {"request": request, "user": user, "error": None, "success": None})
    
    @app.post("/change-password")
    async def change_password_post(
        request: Request,
        current_password: str = Form(...),
        new_password: str = Form(...),
        confirm_password: str = Form(...),
        user=Depends(manager)
    ):
        username = user["username"]
        
        # Verify current password
        if users[username]["password"] != current_password:
            return templates.TemplateResponse("change_password.html", {
                "request": request, 
                "user": user,
                "error": "Current password is incorrect",
                "success": None
            })
        
        # Check if new passwords match
        if new_password != confirm_password:
            return templates.TemplateResponse("change_password.html", {
                "request": request,
                "user": user,
                "error": "New passwords do not match",
                "success": None
            })
        
        # Check password strength (optional)
        if len(new_password) < 6:
            return templates.TemplateResponse("change_password.html", {
                "request": request,
                "user": user,
                "error": "Password must be at least 6 characters",
                "success": None
            })
        
        # Update password
        users[username]["password"] = new_password
        save_users()  # Save to file
        
        return templates.TemplateResponse("change_password.html", {
            "request": request,
            "user": user,
            "error": None,
            "success": "Password changed successfully!"
        })