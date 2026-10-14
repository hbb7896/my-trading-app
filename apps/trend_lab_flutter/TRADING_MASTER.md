# Trading Master

기존 Sites Trading Master의 디자인과 기능을 Flutter 웹·Android로 옮긴 독립 실행 화면입니다. 원본 React 소스는 `apps/trading-master`에 보존합니다. 트렌드랩 화면은 독립 앱의 메뉴에 포함하지 않습니다. 로그인과 거래 API만 재사용합니다.

## 실행

```powershell
flutter run -d chrome --target lib/trading_master_main.dart
flutter build web --release --target lib/trading_master_main.dart --output build/trading-master-web
node tool/prepare_master_web.mjs build/trading-master-web
flutter build apk --debug --target lib/trading_master_main.dart --dart-define=API_BASE_URL=https://앱-서버-주소
```

운영 빌드는 Supabase 본인 로그인을 요구합니다. Android는 `Trading Master` 표시 이름과 `com.hbb7896.tradingmaster` 앱 ID를 사용해 트렌드랩과 함께 설치할 수 있습니다. Debug APK는 개발 검증용이며 스토어 배포용 서명은 별도로 준비합니다.

화면 비교용 빌드에만 `--dart-define=MASTER_PREVIEW=true`를 추가합니다. 미리보기는 원본 코드의 48개 샘플 거래를 사용하고 실제 계정의 기록을 읽거나 저장하지 않습니다. 운영 배포에는 이 옵션을 넣지 않습니다. 기존 Sites의 실제 기록은 자동 이전하지 않습니다.

## 원본과 같은 구성

- 왼쪽 WORKSPACE·분석 도구 메뉴, 개인 저널 헤더, 기간 선택·가져오기·내보내기
- 대시보드의 네 개 지표 카드, 누적 손익·월별 손익, 최근 거래·Trading DNA
- 월별·연도별 성적표, 거래표와 검색, 실수 태그·복기 상태
- DNA·Big Winner·보유기간·Risk·최근 구간 비교
- Victor 손익비 산점도, 평균 손실금 기준 R-배수, 수익률 분포·왜도
- 미너비니 연도별 월간 확인표·장기 평균, 목표수익 계산기·내 기록 반영
- 기록에 근거한 미너비니 복기 질문과 일시적 체크리스트
- 개별 매매일지의 차트 링크·메모·실수 태그·심리·규율, 거래 등록·수정·삭제

원본의 DM Sans·Noto Sans KR 글꼴과 색상 값을 사용합니다. Flutter 위젯과 차트 렌더러를 사용하므로 브라우저 종류와 글자 렌더링에 따라 세부 모양은 달라질 수 있습니다.

## 가져오기

원본과 같은 SheetJS 0.20.3과 키움 변환 규칙으로 `.xlsx`·`.xls`·UTF-8/CP949 CSV를 읽습니다. 시트·제목 행·열 연결·실현손익/체결 유형을 확인하고 등록 미리보기를 거쳐 저장합니다. 체결 자료는 선입선출(FIFO), 수수료·세금, 같은 날 순서 옵션을 지원합니다. 완료되지 않은 보유량과 제외한 행을 표시합니다. 원본 파일은 서버 메모리에서 해석한 뒤 폐기하며 파일로 저장하지 않습니다.

실제 서버의 `/api/workbook/preview`는 본인 인증 뒤에만 사용할 수 있습니다. 등록은 기존 CSV 원자적 가져오기 API를 재사용하고 중복은 제외합니다. 기존 Trading Master 내보내기의 ID·메모·태그·심리·규율·차트 링크도 보존합니다.

## 배포 준비

기존 API 이미지의 웹 빌드 대상을 `lib/trading_master_main.dart`로 지정할 수 있도록 `deploy/trend-lab/Dockerfile.render`에 `FLUTTER_TARGET` 인자를 추가했습니다. Docker 빌드 예:

```text
docker build --build-arg FLUTTER_TARGET=lib/trading_master_main.dart -f deploy/trend-lab/Dockerfile.render -t trading-master .
```

실제 외부 서비스 생성·배포와 실제 기록 이전은 별도의 운영 단계입니다. GitHub Actions는 트렌드랩과 트레이딩 마스터의 웹·Android 산출물을 각각 생성합니다.
