import bcrypt
hash_str = b"$2b$12$i78VIoTViXMFI/y5yWhVZ.TcCZy9uvVv4rLlkUkghv7My475LpHcm"
try:
    print("bcrypt.checkpw:", bcrypt.checkpw(b"password", hash_str))
except Exception as e:
    print("Error:", type(e), e)
