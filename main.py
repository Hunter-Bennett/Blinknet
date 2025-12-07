#uvicorn main:app --reload

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import socket
import time
import json
import os
from threading import Thread
from auth import manager, login_routes, save_users, load_users
from fastapi import Depends
from starlette.middleware.base import BaseHTTPMiddleware

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# File paths for persistent storage
DEVICES_FILE = "devices.json"

# Load devices from file
def load_devices():
    if os.path.exists(DEVICES_FILE):
        try:
            with open(DEVICES_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

# Save devices to file
def save_devices():
    with open(DEVICES_FILE, 'w') as f:
        json.dump(devices, f, indent=2)

# In-memory device storage (loaded from file)
devices = load_devices()
next_id = max([d["id"] for d in devices], default=0) + 1

CHECK_INTERVAL = 2  # seconds
SMOOTHING_COUNT = 3 # consecutive failures to mark offline

class RedirectUnauthorizedMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow public access to login, logout, and static files
        if request.url.path in ["/login", "/logout"] or request.url.path.startswith("/static"):
            return await call_next(request)
        
        # Check if user has a valid token cookie
        token = request.cookies.get(manager.cookie_name)
        if not token:
            # No token, redirect to login
            return RedirectResponse(url="/login", status_code=303)
        
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            # If Unauthorized, redirect to login
            if hasattr(e, "status_code") and e.status_code == 401:
                return RedirectResponse(url="/login", status_code=303)
            raise e

app.add_middleware(RedirectUnauthorizedMiddleware)

# Register login routes BEFORE the middleware checks them
login_routes(app, templates)

# ----------------------
# Device check functions
# ----------------------
def check_tcp(ip, port, timeout=2):
    """Return latency in ms if reachable, else None"""
    start = time.time()
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            latency = (time.time() - start) * 1000
            return round(latency, 2)
    except Exception:
        return None

def update_device_status(device):
    latency = check_tcp(device["ip"], device["port"])
    online = latency is not None

    # Append status for smoothing
    device.setdefault("status_history", []).append(online)
    if len(device["status_history"]) > SMOOTHING_COUNT:
        device["status_history"].pop(0)

    # Decide final online status
    device["is_online"] = all(device["status_history"]) if not online else True
    device["latency"] = latency
    # Keep last 20 latencies for graph
    device.setdefault("history", []).append(latency if latency is not None else 0)
    if len(device["history"]) > 20:
        device["history"].pop(0)

def background_status_updater():
    while True:
        for device in devices:
            update_device_status(device)
        time.sleep(CHECK_INTERVAL)

# Start background thread
thread = Thread(target=background_status_updater, daemon=True)
thread.start()

# Helper function to get user's devices
def get_user_devices(username):
    return [d for d in devices if d.get("owner") == username]

# ----------------------
# Routes
# ----------------------
@app.get("/")
async def dashboard(request: Request, user=Depends(manager)):
    username = user["username"]
    user_devices = get_user_devices(username)
    return templates.TemplateResponse("dashboard.html", {"request": request, "devices": user_devices, "user": user})

@app.post("/add")
async def add_device(name: str = Form(...), ip: str = Form(...), protocol: str = Form(...), port: int = Form(...), user=Depends(manager)):
    global next_id
    username = user["username"]
    
    devices.append({
        "id": next_id,
        "name": name,
        "ip": ip,
        "protocol": protocol,
        "port": port,
        "owner": username,  # Add owner field
        "latency": None,
        "is_online": False,
        "history": [],
        "status_history": []
    })
    next_id += 1
    save_devices()  # Save to file
    return RedirectResponse("/", status_code=303)

@app.post("/edit")
async def edit_device(device_id: int = Form(...), name: str = Form(...), ip: str = Form(...), protocol: str = Form(...), port: int = Form(...), user=Depends(manager)):
    username = user["username"]
    
    for device in devices:
        if device["id"] == device_id and device.get("owner") == username:  # Check ownership
            device.update({"name": name, "ip": ip, "protocol": protocol, "port": port})
            device["status_history"] = []  # reset smoothing for new IP/port
            break
    save_devices()  # Save to file
    return RedirectResponse("/", status_code=303)

@app.post("/delete")
async def delete_device(device_id: int = Form(...), user=Depends(manager)):
    global devices
    username = user["username"]
    
    # Only delete if user owns the device
    devices = [d for d in devices if not (d["id"] == device_id and d.get("owner") == username)]
    save_devices()  # Save to file
    return RedirectResponse("/", status_code=303)

@app.get("/api/status")
async def api_status(user=Depends(manager)):
    """Return JSON for dashboard JS - only user's devices"""
    username = user["username"]
    user_devices = get_user_devices(username)
    
    return JSONResponse([
        {
            "id": d["id"],
            "name": d["name"],
            "ip": d["ip"],
            "latency": d["latency"],
            "is_online": d["is_online"],
            "history": d["history"]
        } for d in user_devices
    ])

@app.get("/settings")
async def settings_page(request: Request, user=Depends(manager)):
    return templates.TemplateResponse("settings.html", {"request": request})

@app.get("/about")
async def about_page(request: Request, user=Depends(manager)):
    return templates.TemplateResponse("about.html", {"request": request})