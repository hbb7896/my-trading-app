import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:trend_lab/api.dart';
import 'package:trend_lab/trade.dart';

void main() {
  test(
    'both editors share create/update records and retain journal fields',
    () async {
      final records = <Map<String, dynamic>>[];
      final client = MockClient((request) async {
        if (request.method == 'POST') {
          records.add({'id': 'shared-id', ...jsonDecode(request.body) as Map});
        } else if (request.method == 'PUT') {
          expect(request.url.path, '/api/trades/shared-id');
          records[0] = {'id': 'shared-id', ...jsonDecode(request.body) as Map};
        }
        return http.Response(
          jsonEncode(request.method == 'GET' ? records : {}),
          200,
          headers: {'content-type': 'application/json; charset=utf-8'},
        );
      });
      await http.runWithClient(() async {
        final api = TradingApi('https://example.test', 'test-token');
        var labRefreshes = 0, masterRefreshes = 0;
        api.addListener(() => labRefreshes++);
        api.addListener(() => masterRefreshes++);
        await api.save(
          const Trade(
            ticker: '공유 테스트',
            code: '005930',
            entry: '2026-01-01',
            exit: '2026-01-05',
            buy: 100,
            sell: 110,
            memo: '진입 근거',
            extra: {
              'tags': ['계획'],
              'emotion': '차분함',
            },
          ),
        );
        final masterRecord = (await api.trades()).single;
        await api.save(
          Trade(
            id: masterRecord.id,
            ticker: masterRecord.ticker,
            code: masterRecord.code,
            entry: masterRecord.entry,
            exit: masterRecord.exit,
            buy: masterRecord.buy,
            sell: 120,
            memo: masterRecord.memo,
            extra: masterRecord.extra,
          ),
        );
        final labRecord = (await api.trades()).single;
        expect(records, hasLength(1));
        expect(labRecord.sell, 120);
        expect(labRecord.memo, '진입 근거');
        expect(labRecord.extra['tags'], ['계획']);
        expect(labRecord.extra['emotion'], '차분함');
        expect(labRefreshes, 2);
        expect(masterRefreshes, 2);
        api.dispose();
      }, () => client);
    },
  );
}
