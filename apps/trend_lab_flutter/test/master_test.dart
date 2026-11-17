import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trend_lab/master_metrics.dart';
import 'package:trend_lab/trading_master.dart';
import 'package:trend_lab/trade.dart';

Trade trade(String id, double buy, double sell) => Trade(
  id: id,
  ticker: '테스트 $id',
  code: '',
  entry: '2026-01-01',
  exit: '2026-02-01',
  buy: buy,
  sell: sell,
);
void main() {
  test('metrics distinguish return ratios from monetary profit factor', () {
    final m = MasterMetrics([
      trade('a', 100, 120),
      trade('b', 200, 180),
      trade('c', 100, 100),
    ]);
    expect(m.net, 0);
    expect(m.winRate, closeTo(100 / 3, 1e-9));
    expect(m.rewardRisk, closeTo(2, 1e-9));
    expect(m.profitFactor, 1);
    expect(m.expectancy, closeTo(10 / 3, 1e-9));
    expect(m.adjustedRewardRisk, 2);
    expect(m.averageDays(true), 31);
    expect(MasterMetrics([]).profitFactor, isNull);
    expect(MasterMetrics([trade('a', 100, 120)]).rewardRisk, double.infinity);
  });
  test('target uses portfolio position and does not round exact trades up', () {
    final r = TargetResult(
      portfolio: 10000000,
      position: 20,
      target: 10,
      win: 15,
      loss: 5,
      success: 50,
    );
    expect(r.positionAmount, 2000000);
    expect(r.expectancy, 5);
    expect(r.trades, 10);
    expect(
      TargetResult(
        portfolio: 100,
        position: 20,
        target: 10,
        win: 5,
        loss: 5,
        success: 50,
      ).trades,
      isNull,
    );
  });
  test('CSV preserves quoted multiline memo and journal metadata', () {
    final csv = masterCsv([
      const Trade(
        id: 'id',
        ticker: '가,나',
        code: '',
        entry: '',
        exit: '2026-01-01',
        buy: 100,
        sell: 110,
        memo: '"계획"\n복기',
        extra: {
          'tags': ['추격매수', '기타'],
          'emotion': '차분',
          'discipline': '준수',
        },
      ),
    ]);
    expect(csv, startsWith('\uFEFF'));
    expect(csv, contains('"가,나"'));
    expect(csv, contains('""계획""\n복기'));
    expect(csv, contains('추격매수|기타'));
  });
  testWidgets('every master section fits phone and desktop', (tester) async {
    for (final size in [const Size(390, 844), const Size(1400, 1000)]) {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.dark(),
          home: TradingMasterScreen(
            initialTrades: [trade('수익', 100, 120), trade('손실', 200, 180)],
          ),
        ),
      );
      await tester.pump();
      for (int i = 0; i < masterSections.length; i++) {
        if (size.width < 760) {
          await tester.tap(find.byTooltip('메뉴 열기'));
          await tester.pumpAndSettle();
        }
        await tester.ensureVisible(find.byKey(ValueKey('master-nav-$i')));
        await tester.tap(find.byKey(ValueKey('master-nav-$i')));
        await tester.pumpAndSettle();
        expect(
          tester.takeException(),
          isNull,
          reason: '${masterSections[i]} at $size',
        );
      }
      await tester.pumpWidget(const SizedBox());
    }
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
  });
}
