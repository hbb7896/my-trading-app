import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trend_lab/master_import.dart';
import 'package:trend_lab/master_journal.dart';
import 'package:trend_lab/master_metrics.dart';
import 'package:trend_lab/master_sample.dart';
import 'package:trend_lab/master_target.dart';
import 'package:trend_lab/trading_master.dart';

void main() {
  test('original demo fixture has 48 distinct read-only trades', () {
    final rows = masterSample();
    expect(rows.length, 48);
    expect(rows.map((t) => t.id).toSet().length, 48);
    expect(rows.every((t) => t.id.startsWith('DEMO_')), isTrue);
    expect(MasterMetrics(rows).net, 9576200);
    expect(requiredTradeCount(0, 25, 2.66), 0);
    expect(requiredTradeCount(1e-20, 25, 2.66), 1);
    expect(requiredTradeCount(1e10, 1e-10, 1e-10), isNull);
  });
  testWidgets('sample journal is a page and cannot save to the real database', (
    tester,
  ) async {
    int saves = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: MasterJournalPage(
              trade: masterSample().first,
              onSave: (_) async {
                saves++;
              },
              onBack: () {},
              onEdit: (_) {},
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('삼성전자 매매일지'), findsOneWidget);
    expect(find.text('차트를 첨부해보세요'), findsOneWidget);
    expect(find.text('샘플 거래는 저장할 수 없습니다'), findsOneWidget);
    expect(
      tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
      isNull,
    );
    expect(saves, 0);
    expect(tester.takeException(), isNull);
  });
  testWidgets('record-derived target values replace example assumptions', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: TargetCalculator(stats: MasterMetrics(masterSample())),
          ),
        ),
      ),
    );
    await tester.ensureVisible(find.text('내 기록 반영'));
    await tester.tap(find.text('내 기록 반영'));
    await tester.pumpAndSettle();
    final inputs = tester
        .widgetList<TextField>(find.byType(TextField))
        .toList();
    expect(inputs[0].controller!.text, '100000000');
    expect(inputs[5].controller!.text, '64.58');
    expect(tester.takeException(), isNull);
  });
  testWidgets(
    'original import steps appear without opening a file when logged out',
    (tester) async {
      await tester.pumpWidget(const MaterialApp(home: MasterImportDialog()));
      expect(find.text('키움 거래내역 가져오기'), findsOneWidget);
      await tester.tap(find.text('파일 선택'));
      await tester.pumpAndSettle();
      expect(find.text('실제 파일을 가져오려면 본인 계정으로 로그인하세요.'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'mobile menu navigates through all 10 original pages including lower content',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      await tester.pumpWidget(
        const MaterialApp(home: TradingMasterScreen(preview: true)),
      );
      for (int i = 0; i < masterSections.length; i++) {
        await tester.tap(find.byTooltip('메뉴 열기'));
        await tester.pumpAndSettle();
        await tester.ensureVisible(find.byKey(ValueKey('master-nav-$i')));
        await tester.tap(find.byKey(ValueKey('master-nav-$i')));
        await tester.pumpAndSettle();
        for (int step = 0; step < 3; step++) {
          await tester.drag(
            find.byKey(ValueKey('master-body-$i-false')),
            const Offset(0, -600),
          );
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull, reason: masterSections[i]);
        }
      }
      await tester.pumpWidget(const SizedBox());
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    },
  );
}
