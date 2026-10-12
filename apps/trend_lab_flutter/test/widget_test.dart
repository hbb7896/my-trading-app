import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trend_lab/main.dart';
import 'package:trend_lab/trade.dart';

void main() {
  testWidgets(
    'mobile and desktop show connection state without layout overflow',
    (tester) async {
      for (final size in [const Size(390, 844), const Size(1400, 1000)]) {
        tester.view.physicalSize = size;
        tester.view.devicePixelRatio = 1;
        await tester.pumpWidget(const TrendLabApp());
        await tester.pump();
        expect(find.text('서버 연결하기'), findsOneWidget);
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox());
      }
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    },
  );
  testWidgets('trade editor rejects invalid dates and zero buy', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: TradeEditor())),
    );
    final fields = find.byType(TextFormField);
    for (final pair in <int, String>{
      0: '삼성전자',
      1: '005930',
      2: '2026-02-30',
      3: '2026-03-01',
      4: '0',
      5: '100',
    }.entries) {
      await tester.enterText(fields.at(pair.key), pair.value);
    }
    await tester.tap(find.text('저장'));
    await tester.pump();
    expect(find.text('올바른 날짜를 입력하세요.'), findsOneWidget);
    expect(find.text('올바른 금액을 입력하세요.'), findsOneWidget);
  });
  test('trade metrics use actual amounts', () {
    const t = Trade(
      ticker: 'test',
      code: '005930',
      entry: '2026-01-01',
      exit: '2026-01-02',
      buy: 100,
      sell: 90,
    );
    expect(t.pnl, -10);
    expect(t.roi, -10);
  });
}
