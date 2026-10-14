import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trend_lab/sites_review.dart';

void main() {
  test('APR sample includes matching metrics, seven conditions and future outcomes', () {
    final sample = jsonDecode(
      File('assets/trend_lab_sample.json').readAsStringSync(),
    );
    final r = sample['report'];
    expect(r['closeChange'], closeTo(7.4074074074, 1e-8));
    expect(r['holding'], 28);
    expect(r['sessions'], 20);
    expect(r['range']['up'], closeTo(25.6613756614, 1e-8));
    expect(r['range']['down'], closeTo(-2.7777777778, 1e-8));
    expect(r['criteria'].length, 7);
    expect(r['passed'], 6);
    expect(r['known'], 7);
    expect(r['future'].map((f) => f['date']).toList(), [
      '2026-09-10',
      '2026-09-17',
      '2026-10-06',
    ]);
    for (final pair in [
      (0, -11.0837438424),
      (1, -12.5615763547),
      (2, -10.9605911330),
    ]) {
      expect(r['future'][pair.$1]['change'], closeTo(pair.$2, 1e-8));
    }
    expect(r['observations'].length, 2);
    expect(r['bars'].last['date'], '2026-10-13');
  });
  testWidgets(
    'read-only sample shows all sections and preserves reference interactions',
    (tester) async {
      tester.view.physicalSize = const Size(1012, 884);
      tester.view.devicePixelRatio = 1;
      int calls = 0;
      await tester.runAsync(
        () => rootBundle.loadString('assets/trend_lab_sample.json'),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: SitesReview(
            trades: const [],
            loading: false,
            analyzing: false,
            connected: true,
            sampleData: jsonDecode(
              File('assets/trend_lab_sample.json').readAsStringSync(),
            ) as Map<String, dynamic>,
            analyze: (_) async {
              calls++;
            },
            remove: (_) async {
              calls++;
            },
            edit: (_) async {
              calls++;
            },
            refresh: () async {
              calls++;
            },
            importRecords: () async {
              calls++;
            },
            settings: () async {
              calls++;
            },
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      for (final text in [
        '에이피알',
        '+7.41%',
        '28일',
        '+25.66%',
        '-2.78%',
        '6 / 7',
        '-11.08%',
        '-12.56%',
        '-10.96%',
        '상승 추세 조건',
        '시간이 지난 뒤의 흐름',
        '이번 거래의 복기 질문',
      ]) {
        expect(find.text(text), findsOneWidget);
      }
      expect(calls, 0);
      final paint = find.byKey(const ValueKey('sites-price-chart'));
      await tester.ensureVisible(find.text('앞뒤 120일'));
      await tester.tap(find.text('앞뒤 120일'));
      await tester.pumpAndSettle();
      expect(
        (tester.widget<CustomPaint>(paint).painter as SitesPricePainter).window,
        120,
      );
      await tester.tap(find.byKey(const ValueKey('ma150')));
      await tester.pump();
      expect(
        (tester.widget<CustomPaint>(paint).painter as SitesPricePainter)
            .averages,
        contains(150),
      );
      await tester.ensureVisible(paint);
      await tester.tap(paint);
      await tester.pump();
      final before =
          (tester.widget<CustomPaint>(paint).painter as SitesPricePainter)
              .hovered!;
      await tester.sendKeyEvent(LogicalKeyboardKey.arrowRight);
      await tester.pump();
      expect(
        (tester.widget<CustomPaint>(paint).painter as SitesPricePainter)
            .hovered,
        before + 1,
      );
      tester
          .widget<StickyReviewPair>(find.byType(StickyReviewPair))
          .scroll
          .jumpTo(600);
      await tester.pumpAndSettle();
      expect(tester.getTopLeft(find.text('거래 선택')).dy, greaterThanOrEqualTo(0));
      await tester.ensureVisible(find.text('이 분석으로 알 수 있는 것과 없는 것'));
      await tester.tap(find.text('이 분석으로 알 수 있는 것과 없는 것'));
      await tester.pumpAndSettle();
      expect(find.textContaining('이동평균선과 추세 조건은'), findsOneWidget);
      expect(calls, 0);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    },
  );
}
