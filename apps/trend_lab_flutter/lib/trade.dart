class Trade {
  final String id, ticker, code, entry, exit, memo;
  final double buy, sell;
  const Trade({
    this.id = '',
    required this.ticker,
    required this.code,
    required this.entry,
    required this.exit,
    required this.buy,
    required this.sell,
    this.memo = '',
  });
  double get pnl => sell - buy;
  double get roi => buy > 0 ? pnl / buy * 100 : 0;
  factory Trade.fromJson(Map<String, dynamic> j) => Trade(
    id: j['id'] as String,
    ticker: j['ticker'] as String,
    code: j['code'] as String,
    entry: j['entry'] as String,
    exit: j['exit'] as String,
    buy: (j['buy'] as num).toDouble(),
    sell: (j['sell'] as num).toDouble(),
    memo: j['memo'] as String? ?? '',
  );
  Map<String, dynamic> toJson() => {
    'ticker': ticker,
    'code': code,
    'entry': entry,
    'exit': exit,
    'buy': buy,
    'sell': sell,
    'memo': memo,
  };
}
