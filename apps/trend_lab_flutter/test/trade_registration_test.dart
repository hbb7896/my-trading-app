import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trend_lab/api.dart';
import 'package:trend_lab/trade_registration.dart';
import 'package:trend_lab/open_positions.dart';

class RegistrationApi extends TradingApi {
  final Map<String, dynamic> fixture = jsonDecode(
    File('test/fixtures/capital-accounts.json').readAsStringSync(),
  ) as Map<String, dynamic>;
  final List<String> writes = [];
  Map<String, dynamic>? submitted;
  bool fail = false;
  RegistrationApi() : super('http://test', '');
  @override
  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? body,
  }) async {
    if (method == 'GET') return fixture;
    if (path.endsWith('/unit-plan')) {
      return {
        'quantity': 8,
        'stop': 95000,
        'buyAmount': 800000,
        'unusedBudget': 12500,
      };
    }
    writes.add(path);
    submitted = body;
    if (fail) throw Exception('저장 확인 오류');
    if (path.endsWith('/action')) {
      return {'id': path.split('/')[3], 'accountId': body!['accountId']};
    }
    return {...body!, 'id': 'completed-id'};
  }
}

void main() {
  testWidgets(
    'single registration preserves both drafts and creates only one open position',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      final api = RegistrationApi();
      TradeRegistrationResult? saved;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => TextButton(
                onPressed: () async {
                  saved = await showDialog<TradeRegistrationResult>(
                    context: context,
                    builder: (_) => TradeRegistrationDialog(api: api),
                  );
                },
                child: const Text('등록 열기'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('등록 열기'));
      await tester.pumpAndSettle();
      await tester.enterText(find.widgetWithText(TextField, '종목명'), '보유 검증');
      await tester.enterText(find.widgetWithText(TextField, '매수 가격'), '100000');
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();
      await tester.tap(find.text('지난 청산 거래'));
      await tester.pumpAndSettle();
      expect(find.text('총 매수금액 (원)'), findsOneWidget);
      await tester.enterText(find.byType(TextFormField).at(0), '과거 초안');
      await tester.tap(find.text('새 매수 · 보유 관리'));
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<TextField>(find.widgetWithText(TextField, '종목명'))
            .controller!
            .text,
        '보유 검증',
      );
      await tester.ensureVisible(find.text('체결 저장'));
      await tester.tap(find.text('체결 저장'));
      await tester.pumpAndSettle();
      expect(saved!.cycleId, isNotNull);
      expect(saved!.completed, isNull);
      expect(api.writes.length, 1);
      expect(api.writes.single, endsWith('/action'));
      expect(api.submitted!['quantity'], '8');
      expect(find.text('등록 열기'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
      api.dispose();
    },
  );
  testWidgets(
    'historical mode saves once with selected account and preserves form after an error',
    (tester) async {
      final api = RegistrationApi()..fail = true;
      TradeRegistrationResult? result;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => TextButton(
                onPressed: () async {
                  result = await showDialog<TradeRegistrationResult>(
                    context: context,
                    builder: (_) => TradeRegistrationDialog(api: api),
                  );
                },
                child: const Text('등록 열기'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('등록 열기'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('지난 청산 거래'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('계좌 미분류'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('ISA').last);
      await tester.pumpAndSettle();
      final fields = find.byType(TextFormField);
      await tester.enterText(fields.at(0), '청산 검증');
      await tester.enterText(fields.at(3), '1000');
      await tester.enterText(fields.at(4), '1100');
      await tester.ensureVisible(find.text('거래 저장'));
      await tester.tap(find.text('거래 저장'));
      await tester.pumpAndSettle();
      expect(find.text('저장 확인 오류'), findsOneWidget);
      expect(
        tester.widget<TextFormField>(fields.at(0)).controller!.text,
        '청산 검증',
      );
      api.fail = false;
      await tester.tap(find.text('거래 저장'));
      await tester.pumpAndSettle();
      expect(result!.completed!.ticker, '청산 검증');
      expect(result!.cycleId, isNull);
      expect(api.submitted!['account_id'], 'isa');
      expect(api.writes.every((p) => p == '/api/trades'), isTrue);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      api.dispose();
    },
  );
  testWidgets(
    'trade records list open cycles separately and opens their existing details',
    (tester) async {
      final api = RegistrationApi();
      api.fixture['cycles'] = [
        {
          'id': 'open-id',
          'ticker': '보유 검증',
          'code': '',
          'accountName': 'ISA',
          'quantity': 8,
          'totalR': 0.5,
          'cr': 0.25,
          'e': 0.25,
          'closed': false,
        },
        {'id': 'closed-id', 'closed': true},
      ];
      String? selected;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: OpenPositionsPanel(
                api: api,
                onOpen: (id) => selected = id,
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('보유 중인 거래 · 1건'), findsOneWidget);
      await tester.tap(find.text('보유 검증 · ISA'));
      expect(selected, 'open-id');
      expect(api.writes, isEmpty);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      api.dispose();
    },
  );
}
