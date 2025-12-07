from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
hashed = pwd_context.hash("admin123")
print(f"Hash: {hashed}")

# Test verification
print(f"Verify test: {pwd_context.verify('admin123', hashed)}")