
# Trend Lab · Flutter

하단 메뉴에서 **트렌드랩 / 트레이딩 마스터**를 전환합니다. 두 화면은 동일한 Supabase 로그인, API, 거래 테이블을 사용합니다. 트레이딩 마스터는 대시보드·월별/연도별 성과·거래 기록·Trading DNA·손익비·R-배수·손익 분포·미너비니 지표/복기 질문·목표 계산기를 제공합니다. 각 거래의 매매일지에서 메모·실수 태그·감정·계획 준수·차트 링크를 저장합니다. 화면 전환, 새로고침, 30초 주기로 저장소에서 기록을 다시 읽습니다.

기존 Trading Master 내보내기 CSV를 가져오고, 현재 필터에 표시되는 거래를 같은 열 구조로 내보낼 수 있습니다. 웹에서는 CSV 파일을 다운로드하고, Android/iOS에서는 CSV 내용을 복사하여 시트나 파일 앱에 붙여넣습니다. 원본 React 앱의 저장소나 Google Sheets 자료는 자동 이전하지 않습니다. 거래 수익률의 평균과 계좌 수익률은 다르며, R-배수는 선택 기간의 평균 손실금 기준입니다. 목표 계산기는 고정된 초기 매수금액을 가정합니다.

폰 중심의 개인 매매일지입니다. 안드로이드와 웹이 같은 온라인 데이터베이스를 사용합니다. 거래 등록·수정·삭제·검색, 손익·승률, 일봉 차트와 진입 추세·청산 후 복기, Trading Master CSV 가져오기를 제공합니다.

## 권장 운영 구조

- Flutter: 폰·PC 화면
- Supabase Auth: 본인 계정 로그인과 세션 갱신
- Supabase PostgreSQL: 거래기록 저장과 DB 단계 접근 제한
- API 서버: 계정 검증, 거래 입력 검증, 시세 연결
- GitHub: 코드와 자동 검증
- Google Sheets: 기존 자료 보존과 내보내기·분석용

서버에 `DB_MODE=supabase`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`를 설정합니다. 실제 프로젝트 초기화는 `supabase/README.md`를 따릅니다. 개인용 계정만 허용하고 신규 가입을 닫습니다. 앱이나 API에서 DB 관리자 키를 사용하지 않습니다.

웹은 현재 앱 주소를 API 주소로 사용합니다. 안드로이드 빌드 시 `--dart-define=API_BASE_URL=https://실제-앱-주소`를 지정합니다. API 주소는 공개 값이며 연결 키나 비밀번호를 빌드에 넣지 않습니다.

## 데이터 이전

Trading Master의 **내보내기** CSV를 앱 상단 **기존 기록 가져오기**에서 선택합니다. 파일 미리보기 후 확인한 기록만 저장하며 같은 파일을 다시 가져와도 중복 저장하지 않습니다. 날짜·금액 오류가 있으면 저장을 차단합니다. 진입일·종목코드가 없는 거래는 기록을 보존하고 차트 전에 보완합니다. 메모·태그·심리·규율·차트 링크를 보존합니다.

기존 Google Sheets 구조가 다른 경우 열 매핑을 확인한 뒤 변환해야 합니다. 아직 실제 데이터 이전은 실행하지 않았습니다. 원본 시트를 보존하고 건수·손익을 대조합니다. 양방향 자동 동기화는 사용하지 않습니다.

## 로컬 개발 전용 모드

```powershell
cd apps/trend_lab_flutter
flutter pub get
flutter build web --release
cd ../trend-lab-api
$env:ALLOW_LOCAL_DEV='true'
$env:APP_TOKEN='24자_이상의_로컬_시험용_키'
$env:WEB_DIR='../trend_lab_flutter/build/web'
node server.mjs
```

`http://localhost:8787`에서는 기존 연결 키 방식으로 시험할 수 있습니다. 이 모드의 거래는 로컬 SQLite에만 저장되며 온라인 DB로 자동 이전되지 않습니다. 운영 서버는 Supabase 모드를 설정해야 하고 설정이 없으면 실행을 중단합니다.

## 검증·배포

Flutter 분석·화면 테스트·웹 빌드, API/CSV/인증 테스트, Postgres의 본인·타 계정·미로그인 정책 테스트를 GitHub Actions에서 실행합니다. Android debug APK는 설치 시험용이며 출시 서명은 별도입니다. 실제 프로젝트의 로그인·접근·복원 시험은 계정 연결 후 필요합니다.

웹/API 배포 안내는 `deploy/trend-lab/README.md`에 있습니다. 실제 서비스 생성과 공개 배포는 아직 진행하지 않았습니다.
