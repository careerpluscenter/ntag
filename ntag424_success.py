import os
from smartcard.System import readers
from smartcard.util import toHexString
from Crypto.Cipher import AES
from Crypto.Hash import CMAC
from Crypto.Random import get_random_bytes

# ============================================================================
# [설정] 구글 스크립트 주소
TARGET_URL = "https://script.google.com/macros/s/AKfycbydZ6iVQ20C7NW_ZnIme2YHhgFb_uhNFo58QzmDlV4HlY4b0AgubRbLP7pURVmLJqPGug/exec"
# ============================================================================

DEFAULT_KEY = bytes.fromhex("00000000000000000000000000000000")

def get_connection():
    r = readers()
    if not r: raise Exception("리더기를 찾을 수 없습니다.")
    # ACR1252U PICC (0번)
    connection = r[0].createConnection()
    connection.connect()
    return connection

def send_apdu(conn, apdu, ignore_error=False):
    data, sw1, sw2 = conn.transmit(list(apdu))
    status = (sw1 << 8) | sw2
    if not ignore_error and (status != 0x9100 and status != 0x9000 and status != 0x91AF):
        raise Exception(f"APDU Error: {hex(status)}")
    return bytes(data), status

# [중요] add_padding 함수 삭제함! (라이브러리 자동 기능 사용)

def derive_session_key(key, rnd_a, rnd_b, key_type):
    # SV 구성 (32바이트)
    sv = bytearray()
    if key_type == 1: # EncKey
        sv.extend(bytes.fromhex("A55A00010080"))
    else: # MacKey
        sv.extend(bytes.fromhex("5AA500010080"))
    
    sv.extend(rnd_a[0:2])
    xor_1 = bytes(a ^ b for a, b in zip(rnd_a[2:8], rnd_b[0:6]))
    sv.extend(xor_1)
    sv.extend(rnd_b[6:16])
    xor_2 = bytes(a ^ b for a, b in zip(rnd_a[8:16], rnd_b[6:14]))
    sv.extend(xor_2)
    
    # [수정] Raw Data(32바이트) 그대로 전달 -> 라이브러리가 K1 키 사용 (정답)
    c = CMAC.new(key, ciphermod=AES)
    c.update(sv) 
    return c.digest()

def main():
    try:
        conn = get_connection()
        print("🔌 리더기 연결됨")
        
        # 1. 앱 선택
        send_apdu(conn, bytes.fromhex("00A4040007D276000085010100"))
        
        # 2. 인증
        resp, _ = send_apdu(conn, bytes.fromhex("9071000002000000"))
        rnd_b_enc = resp
        
        cipher = AES.new(DEFAULT_KEY, AES.MODE_CBC, iv=bytes(16))
        rnd_b = cipher.decrypt(rnd_b_enc)
        
        rnd_a = get_random_bytes(16)
        rnd_b_prime = rnd_b[1:] + rnd_b[:1]
        token = rnd_a + rnd_b_prime
        
        cipher = AES.new(DEFAULT_KEY, AES.MODE_CBC, iv=bytes(16))
        token_enc = cipher.encrypt(token)
        
        cmd_auth_2 = bytes.fromhex("90AF000020") + token_enc + bytes.fromhex("00")
        resp, _ = send_apdu(conn, cmd_auth_2)
        
        ses_auth_mac_key = derive_session_key(DEFAULT_KEY, rnd_a, rnd_b, 2)
        ti = rnd_a[0:4]
        
        print(f"🔐 인증 성공 (TI: {toHexString(list(ti))})")
        
        # 3. SDM 설정 (브루트포스 - 카운터 0, 1 시도)
        print("⚙️ SDM 설정 시도 중...")
        
        full_url = TARGET_URL + "?data=00000000000000000000000000000000"
        try:
            sdm_offset = full_url.index("?data=") + 5
        except:
            sdm_offset = 20
        
        off_bytes = int(sdm_offset).to_bytes(3, 'little')
        zero = b'\x00\x00\x00'
        
        # Data Params (21 bytes)
        data_params = b'\x40\x00\xE0' + zero + zero + off_bytes + off_bytes + off_bytes + off_bytes
        
        success = False
        # 카운터 0과 1 시도
        for try_counter in [0, 1]:
            print(f"   🔄 시도: CmdCounter {try_counter} ... ", end="")
            
            ctr_bytes = try_counter.to_bytes(2, 'little')
            
            # MAC Input: Cmd(C1) + Ctr + TI + FileNo(02) + Data
            # 총 길이: 1 + 2 + 4 + 1 + 21 = 29바이트
            mac_input = b'\xC1' + ctr_bytes + ti + b'\x02' + data_params
            
            # [핵심 수정] 수동 패딩 제거! Raw Data(29바이트) 전달
            # 라이브러리가 "어? 모자라네?" 하고 K2 키 사용 + 자동 패딩 (정답)
            c = CMAC.new(ses_auth_mac_key, ciphermod=AES)
            c.update(mac_input)
            mac_8bytes = c.digest()[:8]
            
            final_payload = b'\x02' + data_params + mac_8bytes
            cmd_cfs = bytes.fromhex("90C10000") + bytes([len(final_payload)]) + final_payload + bytes([0x00])
            
            resp, sw = send_apdu(conn, cmd_cfs, ignore_error=True)
            
            if sw == 0x9100:
                print("✅ 성공!")
                success = True
                break
            elif sw == 0x911C:
                print("⚠️ 서명 불일치 (다음 카운터 시도)")
            else:
                print(f"❌ 실패 (코드: {hex(sw)})")
                break 
        
        if not success:
            raise Exception("설정 실패. 카드를 뗐다 다시 시도하세요.")

        # 4. URL 쓰기
        print("📄 URL 데이터 쓰는 중...")
        uri_bytes = full_url.encode('utf-8')
        ndef_msg = b'\xD1\x01' + bytes([len(uri_bytes) + 1]) + b'\x55\x04' + uri_bytes
        
        header = bytes.fromhex("908D0000")
        params = bytes.fromhex("02000000") + bytes([len(ndef_msg), 0x00, 0x00]) + ndef_msg
        cmd = header + bytes([len(params)]) + params + bytes([0x00])
        send_apdu(conn, cmd)
        print("✍️ URL 쓰기 완료")

        print("\n🎉 [대성공] 이제 핸드폰을 태그해보세요!")
        print("URL 뒤의 data= 값이 계속 바뀌면 성공입니다.")

    except Exception as e:
        print(f"❌ 오류: {e}")

if __name__ == "__main__":
    main()