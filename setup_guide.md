# NTAG 424 DNA 카드 설정 가이드

NTAG 424 DNA 카드는 보안 기능(SUN Message)을 사용하기 위해 일반적인 텍스트 쓰기가 아닌 **전용 설정**이 필요합니다.

## 1. 준비물
*   **NFC TagWriter by NXP** 앱 (구글 플레이 스토어/앱스토어에서 설치)
*   배포된 웹앱 URL (아래 2단계 참조)

## 2. 웹앱 URL 확인
1.  앱스스크립트 편집기 우측 상단 **[배포]** -> **[새 배포]** 클릭
2.  유형: **웹 앱**
3.  액세스 권한: **모든 사용자 (Anyone)** (필수)
4.  **[배포]** 클릭 후 `https://script.google.com/...` 로 시작하는 URL 복사

## 3. 태그 설정 방법 (NXP TagWriter 앱 기준)

1.  앱 실행 후 **Write tags** -> **New dataset** -> **Link** 선택
2.  **설정 화면**:
    *   **Select Card Type**: **NTAG 424 DNA** 선택
    *   **URI Type**: **Custom URL** 선택
    *   **Enter URL**:
        *   복사한 URL 뒤에 `?data=00000000000000000000000000000000` 을 붙여넣습니다.
        *   **(중요)** `?data=` 뒤에 **숫자 0을 32개** 입력해야 합니다.
        *   **(주의)** `?sdm=...` 이나 `?uid=...` 같은 다른 글자가 뒤에 더 붙어있으면 **무조건 지우세요!** 오직 `?data=00...00`으로 끝나야 합니다.
        *   예시:
            ```text
            https://script.google.com/macros/s/아이디/exec?data=00000000000000000000000000000000
            ```
3.  **미러링 설정 (Configure Mirroring)**:
    *   **Enable SDM Mirroring**: **체크 (ON)**
    *   **Enable UID Mirroring**: **체크 해제 (OFF)** (중요! 불필요한 설정입니다)
    *   **Enable Counter Mirroring**: **체크 해제 (OFF)** (중요! 불필요한 설정입니다)
    *   **SDM Meta Read Access Right**: **00** (또는 Key 0)으로 변경
    *   **Derivation Key for CMAC Calculation**: **00** (또는 Key 0)으로 변경
    *   **Mirroring Offset 설정 (가장 중요!)**:
        *   **증상**: 화면 아래쪽 `SDM MAC Offset` 값이 **79**처럼 낮은 숫자면 **무조건 실패**합니다. (URL 중간을 덮어쓰기 때문)
        *   **해결 방법**:
            1.  URL 입력창에서 `?data=` 뒤의 **첫 번째 0** 앞에 커서를 둡니다.
            2.  화면 아래로 스크롤하여 **SDM MAC Input Offset** 옆의 **[Set Offset]** 버튼을 누릅니다.
            3.  바로 아래 **SDM MAC Offset** 옆의 **[Set Offset]** 버튼도 누릅니다.
            4.  두 숫자가 **100 이상** (URL 길이에 따라 다름)으로 바뀌었는지 확인하세요.
        *   *참고: `PICC Data Offset`은 사용하지 않으므로 무시하거나, UID Mirroring이 체크 해제되어 있는지 다시 확인하세요.*
4.  **Write**:
    *   설정이 완료되면 **SAVE & WRITE**를 누르고 카드를 휴대폰 뒷면에 태그합니다.

## 4. 테스트
*   카드를 태그했을 때 웹 브라우저가 열리고, URL의 `0000...` 부분이 **알 수 없는 긴 영어/숫자 조합**으로 바뀌어 있다면 성공입니다!
*   "출근 완료" 메시지가 뜨는지 확인하세요.

## 5. 문제 해결 (Store failed 오류 발생 시)

만약 **"Store failed"** 오류가 계속 뜬다면, 다음 순서대로 진행해 보세요.

### 1단계: 태그 초기화 (가장 확실한 방법)
기존 설정이 꼬여있을 수 있습니다. 태그를 공장 초기화 상태로 만듭니다.
1.  TagWriter 앱 메인 화면으로 돌아갑니다.
2.  **Tools** -> **Erase tags** 선택.
3.  카드를 태그하여 지웁니다. (성공 시 "Erase successful" 메시지 뜸)
4.  다시 **Write tags** 메뉴로 가서 처음부터 설정을 진행합니다.

### 2단계: File Read Access 확인 (중요)
설정 화면에서 **Access Rights** 관련 항목을 잘 봐야 합니다.
*   **SDM File Read Access Right**: 반드시 **Free (E)** 또는 **Everywhere**로 되어 있어야 합니다.
    *   만약 이것이 **Key 0**으로 되어 있으면, 일반 핸드폰에서 URL을 읽을 수 없어 오류가 납니다.
*   **SDM Meta Read Access Right**: Key 0 (또는 00)
*   **Derivation Key**: Key 0 (또는 00)

### 3단계: Offset 재확인 (실패 원인 1순위)
**"Store failed"의 가장 큰 원인은 Offset 값이 너무 커서입니다.**
*   URL의 `?data=` 뒤에 0을 32개 넣으셨죠?
*   만약 Offset을 **132**로 설정했는데, 실제 0이 시작되는 위치가 **122**라면?
    *   앱은 132번째부터 암호문을 쓰려고 합니다.
    *   하지만 준비된 0은 32개뿐이라, 공간이 모자라서 **URL 범위를 벗어나게 됩니다.**
    *   결과: **Store failed** 발생 + 데이터 깨짐 (`...000Q T kotestpbk` 같은 이상한 문자 생성)

**해결 방법**:
1.  **반드시 태그를 먼저 초기화(Erase)하세요.** (이미 데이터가 깨져서 덮어쓰기 안 될 수 있음)
2.  URL 입력창에서 `?data=` 바로 뒤의 **첫 번째 0** 앞에 커서를 둡니다.
3.  **[Set Offset]**을 눌렀을 때 나오는 숫자를 믿으세요. (아마 120~125 사이일 것입니다.)
4.  **절대로** 커서를 0들의 중간이나 끝에 두고 Offset을 잡지 마세요.

### 4단계: 단계별 저장 (그래도 안 될 때)
한 번에 다 설정하지 말고 나눠서 해보세요.
1.  **Write tags** -> **New dataset** -> **Link**
2.  URL만 입력 (`...exec?data=0000...`) 하고 **미러링 옵션은 켜지 말고** 그냥 **Save & Write**.
3.  성공하면, 다시 **Write tags** -> **Edit** -> 방금 만든 데이터 선택 -> **Next**.
4.  이제 **Configure Mirroring**을 켜고 Offset 설정 후 **Save & Write**.
    *   이렇게 하면 URL 문제인지 미러링 설정 문제인지 확실히 알 수 있습니다.

## 주의사항
*   **Key 값**: 현재 코드는 기본 키(`00...00`)를 사용하도록 설정되어 있습니다. 카드의 키를 변경했다면 코드의 `TAG_SECRET_KEY_HEX`도 변경해야 합니다.
*   **앱 호환성**: 'NFC Tools' 같은 일반 앱은 이 고급 설정을 지원하지 않을 수 있습니다. 꼭 **NXP TagWriter**나 **NFC Developer** 같은 전문 앱을 사용하세요.
