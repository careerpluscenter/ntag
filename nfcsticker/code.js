/**
 * 웹앱으로부터 GET 요청을 받아 처리하는 함수.
 * 테스트용으로 HTML 페이지를 반환합니다.
 * @param {object} e 이벤트 객체 (GET 요청 정보 포함)
 */
  function doGet(e) {
    // 외부 웹사이트에서 사용하므로 JSON 응답만 반환
    const output = ContentService.createTextOutput();
    output.setMimeType(ContentService.MimeType.JSON);
    
    // CORS 헤더는 Google Apps Script에서 자동으로 처리됨
    
    const response = {
        status: 'info',
        message: '이 웹앱은 POST 요청으로만 사용됩니다. 회사 웹사이트를 통해 접근해주세요.'
    };
    
    return output.setContent(JSON.stringify(response));
  }

  /**
   * OPTIONS 요청 처리 (CORS Preflight)
   */
  function doOptions(e) {
    console.log('=== OPTIONS 요청 처리 ===');
    const output = ContentService.createTextOutput();
    output.setMimeType(ContentService.MimeType.JSON);
    
    return output.setContent('');
  }

  /**
   * POST 요청 테스트 함수
   */
  function testPostRequest() {
    console.log('=== POST 요청 테스트 시작 ===');
    
    try {
      // 테스트 데이터 생성
      const testData = {
        uid: 'test_uid_123',
        latitude: 37.5665,
        longitude: 126.9780,
        test_mode: 0
      };
      
      // doPost 함수 직접 호출
      const mockEvent = {
        postData: {
          contents: JSON.stringify(testData)
        },
        parameter: {
          spreadsheet_id: '1gwhEX8dQOKKNGDV0pHv9xEkiVFF9VKAGzuR8NsiIBk4'
        }
      };
      
      console.log('테스트 데이터:', testData);
      console.log('Mock 이벤트:', mockEvent);
      
      // doPost 함수 실행
      const result = doPost(mockEvent);
      console.log('doPost 결과:', result);
      
      return 'POST 테스트 완료: ' + result.getContent();
      
    } catch (error) {
      console.error('POST 테스트 실패:', error);
      return 'POST 테스트 실패: ' + error.message;
    }
  }

  /**
   * 간단한 테스트 함수 (스프레드시트 접근 테스트)
   */
  function testSpreadsheet() {
    console.log('=== 스프레드시트 테스트 시작 ===');
    
    try {
      // 스프레드시트 접근 테스트
      const SPREADSHEET_ID = '1gwhEX8dQOKKNGDV0pHv9xEkiVFF9VKAGzuR8NsiIBk4';
      const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
      console.log('스프레드시트 접근 성공:', spreadsheet.getName());
      
      // 첫 번째 시트 사용
      const sheet = spreadsheet.getSheets()[0];
      console.log('사용할 시트:', sheet.getName());
      
      // 테스트 데이터 추가
      const now = new Date();
      const testData = [
        now.toLocaleString(),
        'test_' + Date.now(),
        '출근 기록'
      ];
      
      const nextRow = sheet.getLastRow() + 1;
      sheet.getRange(nextRow, 1, 1, testData.length).setValues([testData]);
      console.log('테스트 데이터 저장 완료:', testData);
      
      return '테스트 성공! 데이터가 저장되었습니다.';
      
    } catch (error) {
      console.error('테스트 실패:', error);
      return '테스트 실패: ' + error.message;
    }
  }

  /**
   * doPost 함수 직접 테스트
   */
  function testDoPost() {
    console.log('=== doPost 직접 테스트 시작 ===');
    
    try {
      // Mock 이벤트 객체 생성
      const mockEvent = {
        parameter: {
          spreadsheet_id: '1gwhEX8dQOKKNGDV0pHv9xEkiVFF9VKAGzuR8NsiIBk4'
        }
      };
      
      console.log('Mock 이벤트:', mockEvent);
      
      // doPost 함수 실행
      const result = doPost(mockEvent);
      const response = JSON.parse(result.getContent());
      
      console.log('doPost 결과:', response);
      return 'doPost 테스트 완료: ' + JSON.stringify(response);
      
    } catch (error) {
      console.error('doPost 테스트 실패:', error);
      return 'doPost 테스트 실패: ' + error.message;
    }
  }

  
  /**
   * 웹앱으로부터 POST 요청을 받아 출근 기록을 처리하는 함수 (GPS 위치 정보 포함)
   * @param {object} e 이벤트 객체 (POST 요청 정보 포함)
   */
  function doPost(e) {
    console.log('=== doPost 함수 호출됨 (GPS 위치 정보 포함) ===');
    console.log('이벤트 객체:', e);
    
    // 응답 객체 설정
    const output = ContentService.createTextOutput();
    output.setMimeType(ContentService.MimeType.JSON);
  
    try {
      // POST 데이터 파싱
      let uid = 'test_' + Date.now();
      let latitude = 0;
      let longitude = 0;
      
      if (e.postData && e.postData.contents) {
        const data = JSON.parse(e.postData.contents);
        uid = data.uid || uid;
        latitude = parseFloat(data.latitude) || 0;
        longitude = parseFloat(data.longitude) || 0;
        console.log('받은 데이터:', { uid, latitude, longitude });
      }
      
      // 고정된 스프레드시트 ID 사용
      const SPREADSHEET_ID = '1gwhEX8dQOKKNGDV0pHv9xEkiVFF9VKAGzuR8NsiIBk4';
      console.log('스프레드시트 ID:', SPREADSHEET_ID);
      
      // 스프레드시트 접근
      const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
      console.log('스프레드시트 접근 성공:', spreadsheet.getName());
      
      // 기본 시트 사용 (첫 번째 시트)
      const sheet = spreadsheet.getSheets()[0];
      console.log('사용할 시트:', sheet.getName());
      
      // 현재 시간
      const now = new Date();
      const nextRow = sheet.getLastRow() + 1;
      
      // GPS 위치 정보를 포함한 데이터 (시간, UID, GPS좌표)
      const rowData = [
        now.toLocaleString(), 
        uid, 
        `${latitude}, ${longitude}`
      ];
      
      console.log('데이터 저장 시도:', { nextRow, rowData });
      
      // 데이터 저장
      sheet.getRange(nextRow, 1, 1, rowData.length).setValues([rowData]);
      console.log('데이터 저장 완료!');
  
      // 성공 응답
      return output.setContent(JSON.stringify({ 
        status: 'success', 
        message: '출근 기록이 완료되었습니다.',
        data: rowData
      }));
  
    } catch (error) {
      console.error('doPost 오류:', error);
      return output.setContent(JSON.stringify({ 
        status: 'error', 
        message: '오류 발생: ' + error.message 
      }));
    }
  }

  /**
   * 클라이언트에서 호출하는 함수 (doPost 로직과 동일)
   * @param {object} data 클라이언트에서 전송한 데이터
   */
  function saveAttendanceData(data) {
    try {
      console.log('processAttendance 호출됨:', data);
      
      // doPost와 동일한 로직을 실행
      const mockEvent = {
        postData: {
          contents: JSON.stringify(data)
        }
      };
      
      const result = doPost(mockEvent);
      const response = JSON.parse(result.getContent());
      
      console.log('processAttendance 결과:', response);
      return response;
      
    } catch (error) {
      console.error('processAttendance 에러:', error);
      return {
        status: 'error',
        message: 'processAttendance 함수 실행 중 오류: ' + error.message
      };
    }
  }

  