from smartcard.System import readers
r = readers()
print("연결된 리더기 목록:")
for i, reader in enumerate(r):
    print(f"{i}: {reader}")