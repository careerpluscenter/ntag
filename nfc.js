/**
 * NTAG 424 DNA 근태 관리 시스템 (Server-Side)
 * * 기능:
 * 1. NFC 태그의 암호화된 파라미터 수신
 * 2. AES-128 복호화 수행
 * 3. UID 및 카운터 추출
 * 4. 중복 태그(Replay Attack) 방지
 * 5. 구글 시트 기록
 */

// ----------------------------------------------------------
// [설정 영역]
// ----------------------------------------------------------

// 1. NTAG 424 DNA AES Key
// 보안을 위해 '프로젝트 설정 > 스크립트 속성'에 'TAG_SECRET_KEY'라는 이름으로 저장하는 것을 권장합니다.
// 값이 없으면 아래 기본값을 사용합니다.
const TAG_SECRET_KEY_HEX = PropertiesService.getScriptProperties().getProperty('TAG_SECRET_KEY') || "00000000000000000000000000000000";

// 2. 기록할 구글 시트의 ID
const SPREADSHEET_ID = "1gwhEX8dQOKKNGDV0pHv9xEkiVFF9VKAGzuR8NsiIBk4";

// 3. 시트 이름
const SHEET_NAME = "timetable";

// ----------------------------------------------------------

// 웹앱 접속 시 실행되는 함수 (GET 요청 처리)
function doGet(e) {
    // 1. 파라미터 수신
    const encryptedData = e.parameter.data || e.parameter.p;
    const cmac = e.parameter.cmac || ""; // CMAC 파라미터 추가

    if (!encryptedData) {
        return renderPage("오류", "잘못된 접근입니다. NFC 태그를 통해 접속해주세요.", "error");
    }

    try {
        // 2. 복호화 및 데이터 추출
        const decryptedInfo = decryptNTAG424(encryptedData, TAG_SECRET_KEY_HEX);
        const uid = decryptedInfo.uid;
        const counter = decryptedInfo.counter;

        // 3. 데이터 검증 및 저장
        const result = processAttendance(uid, counter, cmac);

        if (result.success) {
            return renderPage("출근 완료", `안녕하세요, ${uid}님!\n출근이 등록되었습니다.\n(인증회차: ${counter})`, "success");
        } else {
            return renderPage("등록 실패", result.message, "warning");
        }

    } catch (error) {
        return renderPage("인증 실패", "보안 코드를 해독할 수 없습니다.\n관리자에게 문의하세요.\n" + error.message, "error");
    }
}


// NTAG 424 DNA 암호 해독 함수 (AES-128)
function decryptNTAG424(encryptedHex, keyHex) {
    // CryptoJS 라이브러리 체크
    if (typeof CryptoJS === 'undefined') {
        throw new Error("CryptoJS 라이브러리가 필요합니다.\n[라이브러리 ID: 110acA-qaM0HlH4wK3GZwacT1_fLci00Z]");
    }

    const key = CryptoJS.enc.Hex.parse(keyHex);
    const iv = CryptoJS.enc.Hex.parse("00000000000000000000000000000000"); // Standard NTAG 424 IV

    try {
        const decrypted = CryptoJS.AES.decrypt(
            { ciphertext: CryptoJS.enc.Hex.parse(encryptedHex) },
            key,
            { iv: iv, mode: CryptoJS.mode.CBC, padding: CryptoJS.pad.ZeroPadding }
        );

        const decryptedHex = decrypted.toString(CryptoJS.enc.Hex).toUpperCase();

        if (!decryptedHex || decryptedHex.length < 20) {
            throw new Error("복호화 데이터 오류");
        }

        const uid = decryptedHex.substring(0, 14);
        const counterHex = decryptedHex.substring(14, 20);
        const counter = parseInt(counterHex, 16);

        return { uid: uid, counter: counter };
    } catch (e) {
        throw new Error("복호화 실패 (키 불일치 또는 데이터 손상)");
    }
}


// 시트 저장 및 중복 검사 로직 (하이브리드 방식: 캐시 + 시트)
function processAttendance(uid, counter, cmac) {
    const lock = LockService.getScriptLock();
    if (!lock.tryLock(5000)) {
        return { success: false, message: "서버가 혼잡합니다. 잠시 후 다시 시도해주세요." };
    }

    try {
        const lastCounterKey = 'LAST_COUNTER_' + uid;
        const scriptProperties = PropertiesService.getScriptProperties();
        let lastCounterVal = scriptProperties.getProperty(lastCounterKey);
        let lastCounter;

        // 1. 캐시(Properties) 확인
        if (lastCounterVal !== null) {
            lastCounter = Number(lastCounterVal);
        } else {
            // 2. 캐시가 없으면 시트에서 '최초 1회' 검색 (기존 데이터 호환성 및 마이그레이션)
            // 이 과정은 각 직원별로 처음 태그할 때만 수행되므로 이후에는 속도가 빠릅니다.
            lastCounter = findMaxCounterFromSheet(uid);
        }

        // 3. 중복 체크
        if (counter <= lastCounter) {
            return { success: false, message: "이미 사용된 태그(URL)입니다.\n(중복된 카운터)" };
        }

        // 4. 데이터 저장
        const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
        const sheet = ss.getSheetByName(SHEET_NAME);

        const timestamp = new Date();
        const key = Utilities.getUuid();

        // 시트 열 구조: A(key), B(uid), C(counter), D(timestamp), E(cmac)
        sheet.appendRow([key, uid, counter, timestamp, cmac]);

        // 5. 캐시 업데이트 (다음번 태그 시 시트 검색 없이 바로 처리됨)
        scriptProperties.setProperty(lastCounterKey, String(counter));

        return { success: true };

    } catch (e) {
        return { success: false, message: "서버 오류: " + e.message };
    } finally {
        lock.releaseLock();
    }
}

// [보조 함수] 시트에서 해당 UID의 가장 높은 카운터 값을 찾음
function findMaxCounterFromSheet(targetUid) {
    try {
        const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
        const sheet = ss.getSheetByName(SHEET_NAME);
        const lastRow = sheet.getLastRow();

        if (lastRow <= 1) return -1; // 데이터 없음

        // 전체 데이터를 메모리로 가져옴 (헤더 제외)
        const data = sheet.getRange(2, 1, lastRow - 1, 3).getValues();
        // Column: [Key, ID, Counter]

        let maxCounter = -1;

        for (let i = 0; i < data.length; i++) {
            const rowId = data[i][1];
            const rowCounter = Number(data[i][2]);

            if (String(rowId) === String(targetUid)) {
                if (rowCounter > maxCounter) {
                    maxCounter = rowCounter;
                }
            }
        }
        return maxCounter;
    } catch (e) {
        console.error("시트 검색 중 오류: " + e.message);
        return -1; // 오류 시 안전하게 통과시키거나( -1 ), 보수적으로 막을 수 있음
    }
}


// HTML 페이지 렌더링 헬퍼 함수
function renderPage(title, message, type) {
    const template = HtmlService.createTemplateFromFile('response');
    template.title = title;
    template.message = message;
    template.type = type; // 'success', 'error', 'warning'
    return template.evaluate()
        .setTitle("근태 체크")
        .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}