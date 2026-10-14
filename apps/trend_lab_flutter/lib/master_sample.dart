import 'trade.dart';

/// Original Sites demo fixture. Never written to the owner's database.
List<Trade> masterSample() {
  const rois = [
    8.3,
    -3.8,
    12.7,
    5.4,
    -5.5,
    18.2,
    -2.9,
    7.4,
    24.8,
    -4.2,
    11.2,
    3.1,
    -8.9,
    15.8,
    -2.7,
    6.5,
    32.4,
    -4.8,
    10.6,
    -12.3,
    9.5,
    4.8,
    -3.2,
    21.6,
    7.8,
    -5.1,
    13.4,
    -3.5,
    8.9,
    16.2,
    4.3,
    -4.6,
    26.5,
    -3.9,
    11.8,
    6.7,
    -7.2,
    19.3,
    8.6,
    -2.8,
    14.5,
    5.2,
    -4.1,
    22.7,
    9.2,
    -3.6,
    17.4,
    6.8,
  ];
  const names = [
    '삼성전자',
    'SK하이닉스',
    'NAVER',
    '현대차',
    '한화에어로스페이스',
    '두산에너빌리티',
    '알테오젠',
    '기아',
  ];
  const amounts = [2400000.0, 3200000.0, 1800000.0, 4100000.0, 2700000.0];
  return List.generate(rois.length, (i) {
    final exit = DateTime.utc(2026, 4, 3 + i * 3),
        entry = exit.subtract(Duration(days: 2 + (i * 7) % 24)),
        buy = amounts[i % 5];
    return Trade(
      id: 'DEMO_${i.toString().padLeft(3, '0')}',
      ticker: names[i % 8],
      code: '',
      entry: entry.toIso8601String().substring(0, 10),
      exit: exit.toIso8601String().substring(0, 10),
      buy: buy,
      sell: (buy * (1 + rois[i] / 100)).roundToDouble(),
      memo: i % 7 == 0
          ? '계획한 목표보다 빠르게 청산. 다음 거래에서는 청산 기준을 먼저 확인하기.'
          : '진입 근거와 청산 계획을 확인한 거래.',
      extra: {
        'tags': i % 7 == 0
            ? ['조기청산']
            : rois[i] < -7
            ? ['손절 지연']
            : [],
        'emotion': '',
        'discipline': '',
      },
    );
  });
}
