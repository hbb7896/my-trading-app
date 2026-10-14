import 'dart:math' as math;

import 'trade.dart';

double mean(Iterable<num> values) => values.isEmpty
    ? 0
    : values.fold<double>(0, (a, b) => a + b) / values.length;
double? divide(double a, double b) => b > 0
    ? a / b
    : a > 0
    ? double.infinity
    : null;
String ratio(double? value) => value == null
    ? '—'
    : value.isInfinite
    ? '∞'
    : value.toStringAsFixed(2);
int? holding(Trade t) {
  final a = DateTime.tryParse(t.entry), b = DateTime.tryParse(t.exit);
  return a == null || b == null ? null : b.difference(a).inDays;
}

class MasterMetrics {
  final List<Trade> trades;
  MasterMetrics(Iterable<Trade> values) : trades = values.toList();
  List<Trade> get wins => trades.where((t) => t.pnl > 0).toList();
  List<Trade> get losses => trades.where((t) => t.pnl < 0).toList();
  int get n => trades.length;
  double get net => trades.fold(0, (a, t) => a + t.pnl);
  double get grossProfit => wins.fold(0, (a, t) => a + t.pnl);
  double get grossLoss => losses.fold(0, (a, t) => a - t.pnl);
  double get winRate => n == 0 ? 0 : wins.length / n * 100;
  double get averageWin => mean(wins.map((t) => t.roi));
  double get averageLoss => mean(losses.map((t) => -t.roi));
  double get expectancy => mean(trades.map((t) => t.roi));
  double? get profitFactor => divide(grossProfit, grossLoss);
  double? get rewardRisk => divide(averageWin, averageLoss);
  double? get adjustedRewardRisk =>
      divide(averageWin * wins.length, averageLoss * losses.length);
  double get bigThreshold => averageLoss > 0 ? averageLoss * 2 : 10;
  List<Trade> get big => wins.where((t) => t.roi >= bigThreshold).toList();
  double get contribution => grossProfit == 0
      ? 0
      : big.fold<double>(0, (a, t) => a + t.pnl) / grossProfit * 100;
  double? averageDays(bool winners) {
    final values = (winners ? wins : losses)
        .map(holding)
        .whereType<int>()
        .where((d) => d >= 0);
    return values.isEmpty ? null : mean(values);
  }

  List<Trade> get ordered => [...trades]
    ..sort((a, b) {
      final v = a.exit.compareTo(b.exit);
      return v != 0 ? v : a.id.compareTo(b.id);
    });
  MasterMetrics get recent => MasterMetrics(ordered.skip(math.max(0, n - 20)));
  MasterMetrics get previous => MasterMetrics(
    ordered.skip(math.max(0, n - 40)).take(math.max(0, math.min(20, n - 20))),
  );
  int streak(bool winning) {
    int current = 0, best = 0;
    for (final t in ordered) {
      current = (winning ? t.pnl > 0 : t.pnl < 0) ? current + 1 : 0;
      best = math.max(best, current);
    }
    return best;
  }

  String get dnaType {
    final rr = rewardRisk ?? 0;
    if (rr >= 2 && winRate < 50) return 'Trend Follower';
    if (winRate >= 60 && rr < 1.5) return 'High Accuracy Trader';
    if (rr >= 1.5 && winRate >= 45) return 'Balanced Trader';
    if (contribution >= 60) return 'Big Winner Hunter';
    return 'Developing Edge';
  }

  String get edgeStatus {
    if (previous.n < 5) return '데이터 축적 중';
    int score = 0;
    void compare(
      double? a,
      double? b,
      double threshold, {
      bool inverse = false,
      int weight = 1,
    }) {
      if (a == null || b == null || !a.isFinite || !b.isFinite) return;
      final d = (a - b) * (inverse ? -1 : 1);
      if (d > threshold) {
        score += weight;
      } else if (d < -threshold) {
        score -= weight;
      }
    }

    compare(recent.expectancy, previous.expectancy, .75, weight: 2);
    compare(recent.profitFactor, previous.profitFactor, .2);
    compare(recent.rewardRisk, previous.rewardRisk, .25);
    compare(recent.averageLoss, previous.averageLoss, .5, inverse: true);
    return score >= 2
        ? '개선'
        : score <= -2
        ? '주의'
        : '안정';
  }
}

class TargetResult {
  final double positionAmount, winAmount, lossAmount, expectancy, targetAmount;
  final double? rewardRisk, adjustedRatio, kelly;
  final int? trades;
  TargetResult({
    required double portfolio,
    required double position,
    required double target,
    required double win,
    required double loss,
    required double success,
  }) : positionAmount = portfolio * position / 100,
       winAmount = portfolio * position / 100 * win / 100,
       lossAmount = portfolio * position / 100 * loss / 100,
       expectancy = win * success / 100 - loss * (1 - success / 100),
       targetAmount = portfolio * target / 100,
       rewardRisk = divide(win, loss),
       adjustedRatio = divide(win * success, loss * (100 - success)),
       kelly = win > 0 && loss > 0
           ? math.max(
               0,
               (success / 100 - (1 - success / 100) / (win / loss)) * 100,
             )
           : null,
       trades = requiredTradeCount(
         target,
         position,
         win * success / 100 - loss * (1 - success / 100),
       );
}

int? requiredTradeCount(double target, double position, double expectancy) {
  if (target == 0) return 0;
  if (expectancy <= 0 || position <= 0) return null;
  final count = target / (expectancy * position / 100);
  if (!count.isFinite || count > 9007199254740991) return null;
  return math.max(
    1,
    (count - 2.220446049250313e-16 * math.max(1, count.abs()) * 4).ceil(),
  );
}

String masterCsv(List<Trade> trades) {
  String cell(Object? v) => '"${(v ?? '').toString().replaceAll('"', '""')}"';
  final rows = <List<Object?>>[
    [
      'Trade_ID',
      'Entry_Date',
      'Exit_Date',
      'Holding_Days',
      'Ticker',
      'Buy_Amount',
      'Sell_Amount',
      'P_L_Amount',
      'ROI_Percent',
      'Mistake_Tags',
      'Emotion',
      'Discipline',
      'Memo',
      'Chart_Link',
    ],
    for (final t in trades)
      [
        t.id,
        t.entry,
        t.exit,
        holding(t),
        t.ticker,
        t.buy,
        t.sell,
        t.pnl,
        t.roi,
        (t.extra['tags'] as List? ?? []).join('|'),
        t.extra['emotion'],
        t.extra['discipline'],
        t.memo,
        t.extra['chart_link'],
      ],
  ];
  return '\uFEFF${rows.map((r) => r.map(cell).join(',')).join('\r\n')}';
}
