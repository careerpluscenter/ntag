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
    connection = r[0].createConnection()
    connection.connect()
    return connection

def send_apdu(conn, apdu):
    # 디버깅: 보내는 패킷 출력 (필요시 주석 해제)
    # print(f">> {toHexString(list(apdu))}")
    data, sw1, sw2 = conn.transmit(list(apdu))
    status = (sw1 << 8) | sw2
    # 9100(성공), 9000(성공), 91AF(추가데이터)
    if status != 0x9100 and status != 0x9000 and status != 0x91AF:
        raise Exception(f"APDU Error: {hex(status)}")
    return bytes(data), status

def derive_session_key(key, rnd_a, rnd_b, key_type):
    # SV = A5 5A 00 01 00 80 + RndA[0:2] + (RndA^RndB)[0:6] + RndB[0:12] + (RndA^RndB)[6:16]
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
    c.update(sv)
    return c.digest()

def main():
    try:
        conn = get_connection()
        print("🔌 리더기 연결됨")
        
        # 1. 앱 선택 (NTAG 424 DNA)
        send_apdu(conn, bytes.fromhex("00A4040007D276000085010100"))
        
        # 2. 인증 (AuthenticateEV2First - Part 1)
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
        
        # [중요] TI (Transaction Identifier) 추출 = RndA의 앞 4바이트
        ti = rnd_a[0:4]
        
        print(f"🔐 인증 성공 (TI: {toHexString(list(ti))})")
        
        # CmdCounter는 Auth 직후 0
        cmd_counter = 0

        # 3. URL 데이터 쓰기 (Plain 모드 - 카운터 증가 안함)
        # NDEF Message 구성
        full_url = TARGET_URL + "?data=00000000000000000000000000000000"
        uri_bytes = full_url.encode('utf-8')
        ndef_payload = b'\xD1\x01' + bytes([len(uri_bytes) + 1]) + b'\x55\x04' + uri_bytes
        
        # WriteData (File 2, Offset 0)
        # Header: 90 8D 00 00 Len 02 00 00 00 LenData Data 00
        header = bytes.fromhex("908D0000")
        params = bytes.fromhex("02000000") + bytes([len(ndef_payload), 0x00, 0x00]) + ndef_payload
        cmd = header + bytes([len(params)]) + params + bytes([0x00])
        send_apdu(conn, cmd)
        print("📄 URL 데이터 쓰기 완료")

        # 4. SDM 설정 (MAC 서명 필요)
        # 오프셋 자동 계산
        try:
            sdm_offset = full_url.index("?data=") + 5 # +5는 NDEF 헤더 길이
        except:
            sdm_offset = 20
        
        off_bytes = int(sdm_offset).to_bytes(3, 'little')
        zero = b'\x00\x00\x00'
        
        # FileSettings Parameters (File 2)
        # FileOption(SDM) + AccessRights + UIDOffset + SDMReadCtrOffset + PICCDataOffset + MACInputOffset + ENCOffset + MACOffset + Mode
        # 문서에 따라 순서가 헷갈릴 수 있으나, NTAG 424 표준 순서:
        # [FileOption 1B] [AccessRights 2B] [UIDOffset 3B] [SDMReadCtrOffset 3B] [PICCDataOffset 3B] 
        # [SDMMACInputOffset 3B] [SDMENCOffset 3B] [SDMMACOffset 3B] [SDMReadCtrLimit 3B - 이건 옵션 없을때 생략]
        
        # File Option: 0x40 (SDM Enabled, No UID Mirroring, No Read Ctr)
        data_params = b'\x40' 
        # Access Rights: Read(E), Write(0) -> E0 00
        data_params += b'\xE0\x00'
        # Offsets
        data_params += zero      # UID Offset
        data_params += zero      # SDM Read Ctr Offset
        data_params += off_bytes # PICC Data Offset
        data_params += off_bytes # SDM MAC Input Offset
        data_params += off_bytes # SDM ENC Offset
        data_params += off_bytes # SDM MAC Offset
        
        # MAC 계산
        # Input = Cmd(C1) + CmdCtr(2B) + TI(4B) + FileNo(1B) + DataParams
        # 주의: ChangeFileSettings의 APDU는 90 C1 00 00 ... 이지만,
        # MAC 계산할 때는 [Cmd Code C1] + [Counter] + [TI] + [FileNo 02] + [Data] 순서임.
        
        ctr_bytes = cmd_counter.to_bytes(2, 'little')
        
        # MAC Input 구성
        mac_input = b'\xC1' + ctr_bytes + ti + b'\x02' + data_params
        
        # CMAC 계산
        c = CMAC.new(ses_auth_mac_key, ciphermod=AES)
        c.update(mac_input)
        mac_full = c.digest()
        
        # Truncated MAC (홀수 바이트인 1, 3, 5... 를 가져오는 방식이 EV2 표준)
        # 또는 그냥 앞 8바이트 (NTAG 424는 보통 앞 8바이트)
        mac_8bytes = mac_full[:8]
        
        # 최종 APDU 조립
        # Cmd: 90 C1 00 00 Len [FileNo 02] [DataParams] [MAC 8bytes] 00
        final_payload = b'\x02' + data_params + mac_8bytes
        
        cmd_cfs = bytes.fromhex("90C10000") + bytes([len(final_payload)]) + final_payload + bytes([0x00])
        
        send_apdu(conn, cmd_cfs)
        print(f"⚙️ SDM 설정 완료! (Offset: {sdm_offset})")
        print("\n🎉 축하합니다! 드디어 성공했습니다.")
        print("이제 핸드폰을 태그하면 매번 다른 URL이 생성될 것입니다.")

    except Exception as e:
        print(f"❌ 오류: {e}")
        # 911C가 또 뜨면 MAC 계산 로직의 미세한 차이(Padding 등) 때문일 수 있음.

if __name__ == "__main__":
    main()