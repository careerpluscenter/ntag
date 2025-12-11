import os
from smartcard.System import readers
from smartcard.util import toHexString
from Crypto.Cipher import AES
from Crypto.Hash import CMAC
from Crypto.Random import get_random_bytes

# ============================================================================
# [설정] 구글 스크립트 주소 (Bitly 권장)
TARGET_URL = "https://script.google.com/macros/s/AKfycbydZ6iVQ20C7NW_ZnIme2YHhgFb_uhNFo58QzmDlV4HlY4b0AgubRbLP7pURVmLJqPGug/exec"
# ============================================================================

DEFAULT_KEY = bytes.fromhex("00000000000000000000000000000000")

def get_connection():
    r = readers()
    if not r: raise Exception("리더기를 찾을 수 없습니다.")
    
    # PICC 리더기 찾기 (보통 0번)
    # check_reader.py 결과에서 PICC가 0번이었으므로 0번 선택
    connection = r[0].createConnection()
    connection.connect()
    return connection

def send_apdu(conn, apdu):
    # print(f">> SEND: {toHexString(list(apdu))}") # 디버그용
    data, sw1, sw2 = conn.transmit(list(apdu))
    status = (sw1 << 8) | sw2
    if status != 0x9100 and status != 0x9000 and status != 0x91AF:
        raise Exception(f"APDU Error: {hex(status)}")
    return bytes(data), status

# ISO7816-4 패딩 함수 (데이터 길이를 16배수로 맞춤)
def add_padding(data):
    # 0x80 추가 후 0x00으로 채움
    padded = bytearray(data)
    padded.append(0x80)
    while len(padded) % 16 != 0:
        padded.append(0x00)
    return bytes(padded)

def derive_session_key(key, rnd_a, rnd_b, key_type):
    sv = bytearray()
    if key_type == 1: # EncKey
        sv.extend(bytes.fromhex("A55A00010080"))
    else: # MacKey
        sv.extend(bytes.fromhex("5AA500010080"))
    
    sv.extend(rnd_a[0:2])
    xor_res = bytes(a ^ b for a, b in zip(rnd_a, rnd_b))
    sv.extend(xor_res[0:6])
    sv.extend(rnd_b[0:12])
    sv.extend(xor_res[6:16])
    
    c = CMAC.new(key, ciphermod=AES)
    c.update(add_padding(sv) if len(sv) % 16 != 0 else sv) # SV는 32바이트라 패딩 불필요하지만 안전하게
    return c.digest()

def main():
    try:
        conn = get_connection()
        print("🔌 리더기 연결됨")
        
        # 1. 앱 선택
        send_apdu(conn, bytes.fromhex("00A4040007D276000085010100"))
        
        # 2. 인증 (AuthEV2First Part 1)
        resp, _ = send_apdu(conn, bytes.fromhex("9071000002000000"))
        rnd_b_enc = resp
        
        cipher = AES.new(DEFAULT_KEY, AES.MODE_CBC, iv=bytes(16))
        rnd_b = cipher.decrypt(rnd_b_enc)
        
        # 2-1. RndA 생성 및 Part 2 전송
        rnd_a = get_random_bytes(16)
        rnd_b_prime = rnd_b[1:] + rnd_b[:1]
        token = rnd_a + rnd_b_prime
        
        cipher = AES.new(DEFAULT_KEY, AES.MODE_CBC, iv=bytes(16))
        token_enc = cipher.encrypt(token)
        
        cmd_auth_2 = bytes.fromhex("90AF000020") + token_enc + bytes.fromhex("00")
        resp, _ = send_apdu(conn, cmd_auth_2)
        
        # 2-2. 세션 키 유도
        ses_auth_mac_key = derive_session_key(DEFAULT_KEY, rnd_a, rnd_b, 2)
        
        # TI 추출 (RndA 앞 4바이트)
        ti = rnd_a[0:4]
        
        print(f"🔐 인증 성공 (TI: {toHexString(list(ti))})")
        
        # 3. URL 쓰기 (Plain Mode)
        full_url = TARGET_URL + "?data=00000000000000000000000000000000"
        uri_bytes = full_url.encode('utf-8')
        ndef_payload = b'\xD1\x01' + bytes([len(uri_bytes) + 1]) + b'\x55\x04' + uri_bytes
        
        header = bytes.fromhex("908D0000")
        params = bytes.fromhex("02000000") + bytes([len(ndef_payload), 0x00, 0x00]) + ndef_payload
        cmd = header + bytes([len(params)]) + params + bytes([0x00])
        send_apdu(conn, cmd)
        print("📄 URL 데이터 쓰기 완료")

        # 4. SDM 설정 (ChangeFileSettings)
        # 오프셋 자동 계산
        try:
            sdm_offset = full_url.index("?data=") + 5
        except:
            sdm_offset = 20
        
        off_bytes = int(sdm_offset).to_bytes(3, 'little')
        zero = b'\x00\x00\x00'
        
        # Data Params (File 2)
        # [FileOption 1B] [AccessRights 2B] [UIDOffset 3B] [SDMReadCtrOffset 3B] [PICCDataOffset 3B] 
        # [SDMMACInputOffset 3B] [SDMENCOffset 3B] [SDMMACOffset 3B]
        
        # File Option: 0x40 (SDM Enabled)
        # Access Rights: Read(E), Write(0) -> E0 00
        data_params = b'\x40\xE0\x00' + zero + zero + off_bytes + off_bytes + off_bytes + off_bytes
        
        # MAC 계산 (CmdHeader C1 + Ctr 0000 + TI + FileNo 02 + Data)
        # [핵심 수정] 패딩(0x80...)을 추가해야 911C 에러가 안 남!
        cmd_counter = 0
        ctr_bytes = cmd_counter.to_bytes(2, 'little')
        
        mac_input = b'\xC1' + ctr_bytes + ti + b'\x02' + data_params
        mac_input_padded = add_padding(mac_input) # 패딩 추가!
        
        c = CMAC.new(ses_auth_mac_key, ciphermod=AES)
        c.update(mac_input_padded)
        mac_full = c.digest()
        
        # Truncated MAC (8 bytes) - EV2 uses 1,3,5.. bytes? No, NTAG 424 Standard uses first 8.
        # But if Transaction MAC is enabled... let's stick to standard first 8 bytes.
        mac_8bytes = mac_full[:8]
        
        # 최종 APDU
        final_payload = b'\x02' + data_params + mac_8bytes
        cmd_cfs = bytes.fromhex("90C10000") + bytes([len(final_payload)]) + final_payload + bytes([0x00])
        
        send_apdu(conn, cmd_cfs)
        print(f"⚙️ SDM 설정 완료! (Offset: {sdm_offset})")
        print("\n🎉 축하합니다! 드디어 성공했습니다. 핸드폰을 태그해보세요!")

    except Exception as e:
        print(f"❌ 오류: {e}")

if __name__ == "__main__":
    main()