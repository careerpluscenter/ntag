function doGet(e) {
    // 1. 들어온 데이터 받기
    var params = e.parameter;
    var data = params.data; // 암호화된 인증값 (설정한 ?data= 부분)
    var uid = params.uid;   // 카드 고유번호 (UID Mirroring 설정 시 들어옴)
    
    var now = new Date();   // 현재 시간
    
    // 2. 스프레드시트 연결
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName("출근기록");
    
    // 시트가 없으면 새로 만듭니다.
    if (!sheet) {
      sheet = ss.insertSheet("출근기록");
      // 첫 줄에 제목(헤더) 추가
      sheet.appendRow(["날짜", "시간", "사용자ID(UID)", "인증코드(Data)", "결과"]);
    }
  
    // 3. 데이터 검증 및 처리
    var resultMessage = "✅ 출근 완료";
    var resultStatus = "성공";
    var userId = uid;
  
    // (중요) UID가 안 넘어왔을 경우 처리
    if (!userId) {
      userId = "식별불가";
      resultStatus = "⚠️ UID 없음";
      resultMessage = "❌ 카드는 인식되었으나, 사용자 구분이 안 됩니다.<br>(GoToTags에서 UID Mirroring을 켜주세요)";
    } else {
      // 여기에 나중에 'UID'와 '이름'을 매칭하는 로직을 추가할 수 있습니다.
      // 예: if (userId == "041A2B...") userId = "김철수";
    }
  
    // 4. 시트에 한 줄 추가 (로그 저장)
    sheet.appendRow([
      Utilities.formatDate(now, Session.getScriptTimeZone(), "yyyy-MM-dd"), // 날짜
      Utilities.formatDate(now, Session.getScriptTimeZone(), "HH:mm:ss"),   // 시간
      userId, // UID
      data,   // 인증값
      resultStatus
    ]);
  
    // 5. 핸드폰 화면에 보여줄 결과 페이지 (HTML)
    var htmlTemplate = `
      <!DOCTYPE html>
      <html>
        <head>
          <base target="_top">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <style>
            body { font-family: sans-serif; text-align: center; padding: 50px 20px; background-color: #f0f2f5; }
            .container { background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
            h1 { color: #2ecc71; margin-bottom: 10px; }
            .error { color: #e74c3c; }
            p { color: #555; font-size: 1.1rem; }
            .info { background: #eee; padding: 10px; border-radius: 8px; margin-top: 20px; font-size: 0.9rem; word-break: break-all;}
          </style>
        </head>
        <body>
          <div class="container">
            ${resultStatus == '성공' ? '<h1>' + resultMessage + '</h1>' : '<h1 class="error">확인 필요</h1>'}
            <p><strong>시간:</strong> ${now.toLocaleString()}</p>
            <div class="info">
              <strong>카드번호:</strong> ${userId}<br>
              <strong>인증키:</strong> ${data ? data.substring(0, 10) + "..." : "없음"}
            </div>
            ${resultStatus != '성공' ? '<p style="color:red; font-size:0.8rem;">' + resultMessage + '</p>' : ''}
          </div>
        </body>
      </html>
    `;
  
    return HtmlService.createHtmlOutput(htmlTemplate);
  }