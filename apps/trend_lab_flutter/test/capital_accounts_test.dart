import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:trend_lab/api.dart';
import 'package:trend_lab/capital_accounts.dart';

class CapitalTestApi extends TradingApi {
  Map<String, dynamic>? saved;
  CapitalTestApi() : super('http://test', '');
  @override
  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? body,
  }) async {
    if (path.endsWith('/unit-plan')) {
      return {
        'quantity': 8,
        'stop': 95000,
        'buyAmount': 800000,
        'unusedBudget': 12500,
      };
    }
    saved = body;
    return {};
  }
}

void main() {
  testWidgets(
    'phone account funds compute all four values live and save only capital',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      final api = CapitalTestApi();
      int saves = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: CapitalAccountsPanel(
                api: api,
                accounts: const [
                  {'id': 'dc', 'name': 'DC 퇴직연금', 'capital': ''},
                  {'id': 'isa', 'name': 'ISA', 'capital': ''},
                  {'id': 'general', 'name': '일반', 'capital': ''},
                ],
                onSaved: () async {
                  saves++;
                },
              ),
            ),
          ),
        ),
      );
      await tester.enterText(find.byType(TextField).at(1), '16000000');
      await tester.pump();
      expect(find.text('1E 4,000,000원'), findsOneWidget);
      expect(find.text('1R 200,000원'), findsOneWidget);
      expect(find.text('1유닛 1,000,000원'), findsOneWidget);
      expect(find.text('유닛 위험 50,000원'), findsOneWidget);
      await tester.ensureVisible(find.text('계좌 자금 저장'));
      await tester.tap(find.text('계좌 자금 저장'));
      await tester.pumpAndSettle();
      expect(saves, 1);
      expect((api.saved!['accounts'] as List)[1]['capital'], '16000000');
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
      api.dispose();
    },
  );
  testWidgets(
    'buy price proposes one-unit quantity and five-percent stop; actual fills stay editable',
    (tester) async {
      final api = CapitalTestApi();
      Map<String, dynamic>? fill;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: CapitalBuyDialog(
              api: api,
              account: const {
                'id': 'isa',
                'name': 'ISA',
                'plan': {'unitBudget': 812500, 'oneR': 162500},
              },
              onSave: (v) async {
                fill = v;
              },
            ),
          ),
        ),
      );
      final fields = find.byType(TextField);
      await tester.enterText(fields.at(0), '검증');
      await tester.enterText(fields.at(2), '100000');
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();
      expect(tester.widget<TextField>(fields.at(3)).controller!.text, '8');
      expect(tester.widget<TextField>(fields.at(4)).controller!.text, '95000');
      await tester.enterText(fields.at(3), '7');
      await tester.tap(find.text('체결 저장'));
      await tester.pumpAndSettle();
      expect(fill!['quantity'], '7');
      expect(fill!['accountId'], 'isa');
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      api.dispose();
    },
  );
  test(
    'won formatter keeps fractional unit risk instead of rounding it away',
    () {
      expect(planWon(0.003125), '0.003125원');
      expect(planWon(3250000), '3,250,000원');
    },
  );
}
