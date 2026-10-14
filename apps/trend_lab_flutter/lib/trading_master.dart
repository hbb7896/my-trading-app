import 'dart:async';
import 'dart:convert';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api.dart';
import 'trade.dart';
import 'main.dart' show TradeEditor, money, percent, sign;
import 'master_metrics.dart';
import 'import_dialog.dart';

const masterSections = [
  '대시보드',
  '월별 성과',
  '연도별 성과',
  '거래 기록',
  'Trading DNA',
  '손익비 분석',
  'R-배수 분석',
  '손익 분포',
  '미너비니 지표',
  '미너비니 조언',
  '목표 계산기',
];
const mistakeTags = [
  '추격매수',
  '손절 지연',
  '조기청산',
  '과도한 포지션',
  '계획 없는 진입',
  '재진입 남발',
  '복수매매/뇌동매매',
  '진입 기준 미충족',
  '기타',
];

class TradingMasterScreen extends StatefulWidget {
  final TradingApi? api;
  final List<Trade> initialTrades;
  const TradingMasterScreen({
    super.key,
    this.api,
    this.initialTrades = const [],
  });
  @override
  State<TradingMasterScreen> createState() => _TradingMasterScreenState();
}

class _TradingMasterScreenState extends State<TradingMasterScreen>
    with WidgetsBindingObserver {
  late TradingApi? api;
  late List<Trade> trades;
  Timer? timer;
  bool loading = false;
  String? error;
  int section = 0, days = 0;
  String query = '';
  @override
  void initState() {
    super.initState();
    api = widget.api;
    trades = widget.initialTrades;
    WidgetsBinding.instance.addObserver(this);
    if (api != null) Future.microtask(refresh);
    timer = Timer.periodic(const Duration(seconds: 30), (_) => refresh());
  }

  @override
  void dispose() {
    timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) refresh();
  }

  void notify(Object e) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString().replaceFirst('Exception: ', ''))),
      );
    }
  }

  Future<void> refresh() async {
    if (api == null || loading) return;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final rows = await api!.trades();
      if (mounted) setState(() => trades = rows);
    } catch (e) {
      if (mounted) {
        setState(() => error = e.toString().replaceFirst('Exception: ', ''));
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> connect() async {
    final url = TextEditingController(
      text: const String.fromEnvironment(
        'API_BASE_URL',
        defaultValue: 'http://127.0.0.1:8787',
      ),
    );
    final key = TextEditingController();
    final accepted = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('로컬 미리보기 연결'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: url,
                decoration: const InputDecoration(labelText: '서버 주소'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: key,
                obscureText: true,
                decoration: const InputDecoration(labelText: '개인 연결 키'),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('연결'),
          ),
        ],
      ),
    );
    if (accepted == true && mounted) {
      final u = Uri.tryParse(url.text.trim());
      if (u == null ||
          !['http', 'https'].contains(u.scheme) ||
          u.host.isEmpty ||
          u.userInfo.isNotEmpty ||
          u.query.isNotEmpty ||
          u.fragment.isNotEmpty ||
          key.text.length < 24) {
        notify('서버 주소와 24자 이상의 연결 키를 확인하세요.');
      } else {
        setState(
          () => api = TradingApi(
            url.text.trim().replaceAll(RegExp(r'/+$'), ''),
            key.text,
          ),
        );
        await refresh();
      }
    }
    url.dispose();
    key.dispose();
  }

  Future<void> edit([Trade? t]) async {
    if (api == null) {
      await connect();
      return;
    }
    final value = await showDialog<Trade>(
      context: context,
      builder: (_) => TradeEditor(trade: t),
    );
    if (value != null) {
      try {
        await api!.save(value);
        await refresh();
      } catch (e) {
        notify(e);
      }
    }
  }

  Future<void> journal(Trade t) async {
    if (api == null) {
      await connect();
      return;
    }
    final value = await showDialog<Trade>(
      context: context,
      barrierDismissible: false,
      builder: (_) => MasterJournal(trade: t),
    );
    if (value != null) {
      try {
        await api!.save(value);
        await refresh();
        notify('매매일지를 저장했습니다.');
      } catch (e) {
        notify(e);
      }
    }
  }

  Future<void> remove(Trade t) async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('거래 삭제'),
        content: Text('${t.ticker} 기록을 영구 삭제할까요?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('삭제'),
          ),
        ],
      ),
    );
    if (yes == true && api != null) {
      try {
        await api!.delete(t);
        await refresh();
      } catch (e) {
        notify(e);
      }
    }
  }

  Future<void> importRecords() async {
    if (api == null) {
      await connect();
      return;
    }
    final result = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (_) => ImportDialog(api: api!),
    );
    if (result != null) {
      await refresh();
      notify(result);
    }
  }

  Future<void> export(List<Trade> rows) async {
    try {
      final file = XFile.fromData(
        Uint8List.fromList(utf8.encode(masterCsv(rows))),
        mimeType: 'text/csv',
        name: 'trading-master.csv',
      );
      if (kIsWeb) {
        await file.saveTo('trading-master.csv');
      } else if (defaultTargetPlatform == TargetPlatform.android ||
          defaultTargetPlatform == TargetPlatform.iOS) {
        await Clipboard.setData(ClipboardData(text: masterCsv(rows)));
        notify('CSV ${rows.length}건을 복사했습니다. 시트나 파일 앱에 붙여넣으세요.');
        return;
      } else {
        final location = await getSaveLocation(
          suggestedName: 'trading-master.csv',
        );
        if (location == null) return;
        await file.saveTo(location.path);
      }
      notify('현재 선택한 ${rows.length}건을 내보냈습니다.');
    } catch (e) {
      notify('내보내기를 완료하지 못했습니다: $e');
    }
  }

  List<Trade> get filtered {
    final now = DateTime.now().toUtc().add(const Duration(hours: 9));
    final cutoff = DateTime.utc(
      now.year,
      now.month,
      now.day,
    ).subtract(Duration(days: days));
    return trades.where((t) {
      final date = DateTime.tryParse(t.exit);
      return (days == 0 || (date != null && !date.isBefore(cutoff))) &&
          '${t.ticker} ${t.memo} ${(t.extra['tags'] as List? ?? []).join(' ')}'
              .toLowerCase()
              .contains(query.toLowerCase());
    }).toList();
  }

  Widget box(String title, Widget child, {String? caption}) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w600),
          ),
          if (caption != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                caption,
                style: const TextStyle(color: Colors.white60),
              ),
            ),
          const SizedBox(height: 18),
          child,
        ],
      ),
    ),
  );
  Widget stats(MasterMetrics m) => LayoutBuilder(
    builder: (c, s) {
      final width = s.maxWidth < 600
          ? (s.maxWidth - 12) / 2
          : (s.maxWidth - 36) / 4;
      return Wrap(
        spacing: 12,
        runSpacing: 12,
        children: [
          for (final entry in <String, String>{
            '총 실현 손익': money(m.net),
            '거래수': '${m.n}건',
            '승률': '${m.winRate.toStringAsFixed(1)}%',
            '평균 손익비': ratio(m.rewardRisk),
            'Profit Factor': ratio(m.profitFactor),
            '거래당 기대수익률': percent(m.expectancy),
            '평균 수익률': percent(m.averageWin),
            '평균 손실률': '${m.averageLoss.toStringAsFixed(2)}%',
          }.entries)
            SizedBox(
              width: width,
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        entry.key,
                        style: const TextStyle(
                          color: Colors.white60,
                          fontSize: 12,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Text(
                        entry.value,
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 20,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      );
    },
  );
  Widget table(List<Trade> rows) => Column(
    children: [
      for (final t in rows)
        Card(
          child: ListTile(
            onTap: () => journal(t),
            title: Text('${t.ticker} · ${t.exit}'),
            subtitle: Text(
              '${percent(t.roi)} · 보유 ${holding(t) ?? '—'}일${t.memo.isEmpty ? '' : '\n${t.memo}'}',
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(money(t.pnl), style: TextStyle(color: sign(t.pnl))),
                PopupMenuButton<String>(
                  onSelected: (v) {
                    if (v == 'edit') {
                      edit(t);
                    } else if (v == 'delete') {
                      remove(t);
                    } else {
                      journal(t);
                    }
                  },
                  itemBuilder: (_) => const [
                    PopupMenuItem(value: 'journal', child: Text('매매일지')),
                    PopupMenuItem(value: 'edit', child: Text('거래 수정')),
                    PopupMenuItem(value: 'delete', child: Text('삭제')),
                  ],
                ),
              ],
            ),
          ),
        ),
    ],
  );
  Widget periods(List<Trade> rows, int length) {
    final groups = <String, List<Trade>>{};
    for (final t in rows) {
      groups.putIfAbsent(t.exit.substring(0, length), () => []).add(t);
    }
    final names = groups.keys.toList()..sort((a, b) => b.compareTo(a));
    return box(
      '기간별 상세 성적표',
      SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: DataTable(
          columns: const [
            DataColumn(label: Text('기간')),
            DataColumn(label: Text('손익')),
            DataColumn(label: Text('거래수')),
            DataColumn(label: Text('승률')),
            DataColumn(label: Text('손익비')),
            DataColumn(label: Text('PF')),
            DataColumn(label: Text('기대수익률')),
          ],
          rows: [
            for (final name in [...names, '전체'])
              ...() {
                final m = MasterMetrics(name == '전체' ? rows : groups[name]!);
                return [
                  DataRow(
                    cells: [
                      DataCell(Text(name)),
                      DataCell(Text(money(m.net))),
                      DataCell(Text('${m.n}')),
                      DataCell(Text('${m.winRate.toStringAsFixed(1)}%')),
                      DataCell(Text(ratio(m.rewardRisk))),
                      DataCell(Text(ratio(m.profitFactor))),
                      DataCell(Text(percent(m.expectancy))),
                    ],
                  ),
                ];
              }(),
          ],
        ),
      ),
    );
  }

  Widget distribution(List<Trade> rows) {
    const boundaries = [
      -double.infinity,
      -10.0,
      -5.0,
      0.0,
      5.0,
      10.0,
      20.0,
      double.infinity,
    ];
    const labels = [
      '−10% 미만',
      '−10 ~ −5%',
      '−5 ~ 0%',
      '0 ~ 5%',
      '5 ~ 10%',
      '10 ~ 20%',
      '20% 이상',
    ];
    return box(
      '거래 수익률 분포',
      Column(
        children: [
          for (int i = 0; i < labels.length; i++)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Row(
                children: [
                  SizedBox(width: 110, child: Text(labels[i])),
                  Expanded(
                    child: LinearProgressIndicator(
                      minHeight: 12,
                      value: rows.isEmpty
                          ? 0
                          : rows
                                    .where(
                                      (t) =>
                                          t.roi >= boundaries[i] &&
                                          t.roi < boundaries[i + 1],
                                    )
                                    .length /
                                rows.length,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(
                    '${rows.where((t) => t.roi >= boundaries[i] && t.roi < boundaries[i + 1]).length}건',
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget dna(MasterMetrics m) => Column(
    children: [
      box(
        m.dnaType,
        Text(
          '최근 상태: ${m.edgeStatus}\nBig Winner 기준: +${m.bigThreshold.toStringAsFixed(2)}% · 수익 기여도 ${m.contribution.toStringAsFixed(1)}%\n최대 연속 수익 ${m.streak(true)}회 · 최대 연속 손실 ${m.streak(false)}회',
        ),
      ),
      box(
        '최근 20거래와 직전 최대 20거래',
        m.previous.n < 5
            ? const Text('구간 비교에는 최소 25건의 거래가 필요합니다.')
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '기대수익률: ${percent(m.previous.expectancy)} → ${percent(m.recent.expectancy)}',
                  ),
                  Text(
                    '손익비: ${ratio(m.previous.rewardRisk)} → ${ratio(m.recent.rewardRisk)}',
                  ),
                  Text(
                    'PF: ${ratio(m.previous.profitFactor)} → ${ratio(m.recent.profitFactor)}',
                  ),
                  Text(
                    '평균 손실률: ${m.previous.averageLoss.toStringAsFixed(2)}% → ${m.recent.averageLoss.toStringAsFixed(2)}%',
                  ),
                ],
              ),
      ),
      box('Big Winner 거래', table(m.big)),
    ],
  );
  Widget minervini(MasterMetrics m) => box(
    '미너비니 성과 지표',
    Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '승률 ${m.winRate.toStringAsFixed(2)}% · 수익 ${m.wins.length}건 / 손실 ${m.losses.length}건 / 본전 ${m.n - m.wins.length - m.losses.length}건',
        ),
        const SizedBox(height: 12),
        Text(
          '평균 수익 ${percent(m.averageWin)} · 평균 손실 ${m.averageLoss.toStringAsFixed(2)}%',
        ),
        Text(
          '손익비 ${ratio(m.rewardRisk)} · 조정 손익비 ${ratio(m.adjustedRewardRisk)}',
        ),
        const SizedBox(height: 12),
        Text('수익 거래 평균 보유 ${m.averageDays(true)?.toStringAsFixed(1) ?? '—'}일'),
        Text('손실 거래 평균 보유 ${m.averageDays(false)?.toStringAsFixed(1) ?? '—'}일'),
        const SizedBox(height: 12),
        const Text('조정 손익비 = 평균 수익률 × 수익 거래수 ÷ (평균 손실률 × 손실 거래수).'),
      ],
    ),
  );
  Widget mentor(MasterMetrics m) {
    final largest = m.losses.isEmpty
        ? 0
        : m.losses.map((t) => -t.roi).reduce((a, b) => a > b ? a : b);
    return Column(
      children: [
        box(
          m.n < 20 ? '작은 표본, 일관된 기록부터' : '다음 거래의 준비',
          const Text('나의 기록에서 관찰되는 행동을 돌아보기 위한 질문입니다.'),
        ),
        box(
          '수익과 손실의 균형',
          Text(
            m.n < 5
                ? '거래 기록이 더 쌓일 때까지 성과를 단정하지 마세요.'
                : (m.adjustedRewardRisk ?? 0) < 1
                ? '큰 손실의 청산 과정과 작게 끝난 수익 거래를 각각 복기하세요.'
                : '현재 성과를 만든 진입·청산 기준을 기록하고 유지하세요.',
          ),
        ),
        box(
          '손실을 작게 관리하기',
          Text(
            m.losses.isEmpty
                ? '손실 거래가 없어 손실 통제 능력은 아직 평가할 수 없습니다.'
                : largest >= m.averageLoss * 2 && m.losses.length >= 3
                ? '최대 손실 ${largest.toStringAsFixed(2)}%가 평균의 2배 이상입니다. 청산 실행을 늦춘 이유를 확인하세요.'
                : '최초 청산 계획과 실제 청산 사유를 비교하세요.',
          ),
        ),
        box(
          '매수 규모와 위험의 일관성',
          const Text(
            '총 매수금액만으로 동시 보유 비중을 알 수 없습니다. 실제 보유금액, 청산 기준, 감당할 원화 손실을 함께 기록하세요.',
          ),
        ),
        box(
          '승자와 패자의 보유 습관',
          Text(
            '수익 평균 ${m.averageDays(true)?.toStringAsFixed(1) ?? '—'}일 · 손실 평균 ${m.averageDays(false)?.toStringAsFixed(1) ?? '—'}일\n수익을 일찍 끝낸 이유와 손실을 오래 보유한 이유를 비교하세요.',
          ),
        ),
      ],
    );
  }

  Widget rAnalysis(MasterMetrics m) {
    final risk = m.losses.isEmpty ? 0.0 : m.grossLoss / m.losses.length;
    return box(
      '평균 손실금 기준 R-배수',
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            risk == 0
                ? '손실 거래가 없어 R-배수를 계산할 수 없습니다.'
                : '1R = 평균 손실금 ${money(risk)}\n거래당 기대 R = ${ratio(m.net / m.n / risk)}',
          ),
          const SizedBox(height: 12),
          const Text('개별 거래의 사전 손절 위험금액이 없는 기록입니다. 평균 손실금을 기준으로 계산한 참고 지표입니다.'),
          if (risk > 0)
            for (final t in m.ordered.reversed)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(t.ticker),
                subtitle: Text(t.exit),
                trailing: Text('${ratio(t.pnl / risk)}R'),
              ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final rows = filtered, m = MasterMetrics(rows);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Trading Master'),
        actions: [
          IconButton(
            tooltip: '새로고침',
            onPressed: loading ? null : refresh,
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            tooltip: '거래 등록',
            onPressed: () => edit(),
            icon: const Icon(Icons.add),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: refresh,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              '매매의 결과와 과정을 함께 돌아보는 나의 저널',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<int>(
              initialValue: section,
              decoration: const InputDecoration(labelText: '분석 메뉴'),
              items: [
                for (int i = 0; i < masterSections.length; i++)
                  DropdownMenuItem(value: i, child: Text(masterSections[i])),
              ],
              onChanged: (v) => setState(() => section = v!),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final d in [0, 30, 90, 180, 365])
                  ChoiceChip(
                    label: Text(d == 0 ? '전체' : '$d일'),
                    selected: days == d,
                    onSelected: (_) => setState(() => days = d),
                  ),
                OutlinedButton.icon(
                  onPressed: importRecords,
                  icon: const Icon(Icons.upload_file),
                  label: const Text('CSV 가져오기'),
                ),
                OutlinedButton.icon(
                  onPressed: () => export(rows),
                  icon: const Icon(Icons.download),
                  label: const Text('CSV 내보내기'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search),
                hintText: '종목 · 메모 · 실수 태그 검색',
              ),
              onChanged: (v) => setState(() => query = v),
            ),
            const SizedBox(height: 16),
            if (api == null)
              box(
                '연결 대기',
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('트렌드랩과 같은 서버에 연결하면 같은 거래기록이 표시됩니다.'),
                    TextButton(
                      onPressed: connect,
                      child: const Text('서버 연결하기'),
                    ),
                  ],
                ),
              ),
            if (loading) const LinearProgressIndicator(),
            if (error != null) box('기록을 불러오지 못했습니다', Text(error!)),
            if (rows.isEmpty && !loading)
              section == 10
                  ? const TargetCalculator()
                  : box(
                      '아직 표시할 거래가 없습니다',
                      const Text(
                        '거래를 등록하거나 기존 Trading Master CSV를 가져오세요. 필터도 확인해주세요.',
                      ),
                    )
            else ...[
              if (![3, 10].contains(section)) stats(m),
              const SizedBox(height: 16),
              switch (section) {
                0 => Column(
                  children: [
                    box(
                      '실현 손익의 흐름',
                      SizedBox(
                        height: 180,
                        width: double.infinity,
                        child: CustomPaint(painter: EquityPainter(m.ordered)),
                      ),
                    ),
                    distribution(rows),
                    box('최근 거래', table(m.ordered.reversed.take(8).toList())),
                  ],
                ),
                1 => periods(rows, 7),
                2 => periods(rows, 4),
                3 => table(m.ordered.reversed.toList()),
                4 => dna(m),
                5 => box(
                  '손익비와 기대수익률',
                  Text(
                    '평균 수익 ${percent(m.averageWin)} / 평균 손실 ${m.averageLoss.toStringAsFixed(2)}%\n손익비 ${ratio(m.rewardRisk)} · 승률 ${m.winRate.toStringAsFixed(1)}%\n거래당 기대수익률 ${percent(m.expectancy)}\n\n기대수익률은 거래별 수익률의 단순 평균입니다. 계좌 전체 수익률과는 계산 기준이 다릅니다.',
                  ),
                ),
                6 => rAnalysis(m),
                7 => distribution(rows),
                8 => Column(children: [minervini(m), periods(rows, 7)]),
                9 => mentor(m),
                _ => const TargetCalculator(),
              },
            ],
            const SizedBox(height: 24),
            const Text(
              '트렌드랩과 동일한 거래기록 · 본인 계정 전용',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.white54, fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }
}

class EquityPainter extends CustomPainter {
  final List<Trade> trades;
  EquityPainter(this.trades);
  @override
  void paint(Canvas canvas, Size size) {
    if (trades.isEmpty) return;
    final values = <double>[0];
    for (final t in trades) {
      values.add(values.last + t.pnl);
    }
    final low = values.reduce((a, b) => a < b ? a : b),
        high = values.reduce((a, b) => a > b ? a : b),
        span = high - low;
    final path = Path();
    for (int i = 0; i < values.length; i++) {
      final x = i / (values.length - 1) * size.width,
          y = span == 0
              ? size.height / 2
              : 16 + (high - values[i]) / span * (size.height - 32);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = const Color(0xff75e3bf)
        ..strokeWidth = 2.5
        ..style = PaintingStyle.stroke,
    );
  }

  @override
  bool shouldRepaint(covariant EquityPainter old) => old.trades != trades;
}

class MasterJournal extends StatefulWidget {
  final Trade trade;
  const MasterJournal({super.key, required this.trade});
  @override
  State<MasterJournal> createState() => _MasterJournalState();
}

class _MasterJournalState extends State<MasterJournal> {
  late final TextEditingController memo, emotion, discipline, chart;
  late List<String> tags;
  @override
  void initState() {
    super.initState();
    final t = widget.trade;
    memo = TextEditingController(text: t.memo);
    emotion = TextEditingController(text: t.extra['emotion'] as String? ?? '');
    discipline = TextEditingController(
      text: t.extra['discipline'] as String? ?? '',
    );
    chart = TextEditingController(text: t.extra['chart_link'] as String? ?? '');
    tags = List<String>.from(t.extra['tags'] as List? ?? []);
  }

  @override
  void dispose() {
    for (final c in [memo, emotion, discipline, chart]) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text('${widget.trade.ticker} 매매일지'),
    content: SizedBox(
      width: 540,
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              '${widget.trade.exit} · ${money(widget.trade.pnl)} · ${percent(widget.trade.roi)}',
            ),
            const SizedBox(height: 16),
            const Text('실수 태그'),
            Wrap(
              spacing: 6,
              children: [
                for (final tag in {...mistakeTags, ...tags})
                  FilterChip(
                    label: Text(tag),
                    selected: tags.contains(tag),
                    onSelected: (on) => setState(() {
                      if (on) {
                        tags.add(tag);
                      } else {
                        tags.remove(tag);
                      }
                    }),
                  ),
              ],
            ),
            const SizedBox(height: 16),
            for (final e in {
              memo: '복기 메모',
              emotion: '거래 당시 감정',
              discipline: '계획 준수',
              chart: '차트 링크',
            }.entries)
              Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: TextField(
                  controller: e.key,
                  maxLines: e.key == memo ? 4 : 1,
                  maxLength: e.key == memo ? 10000 : 2048,
                  decoration: InputDecoration(labelText: e.value),
                ),
              ),
          ],
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('취소'),
      ),
      FilledButton(
        onPressed: () {
          final t = widget.trade;
          Navigator.pop(
            context,
            Trade(
              id: t.id,
              ticker: t.ticker,
              code: t.code,
              entry: t.entry,
              exit: t.exit,
              buy: t.buy,
              sell: t.sell,
              memo: memo.text,
              extra: {
                ...t.extra,
                'tags': tags,
                'emotion': emotion.text,
                'discipline': discipline.text,
                'chart_link': chart.text,
              },
            ),
          );
        },
        child: const Text('일지 저장'),
      ),
    ],
  );
}

class TargetCalculator extends StatefulWidget {
  const TargetCalculator({super.key});
  @override
  State<TargetCalculator> createState() => _TargetCalculatorState();
}

class _TargetCalculatorState extends State<TargetCalculator> {
  final inputs = [
    '10000000',
    '20',
    '10',
    '15',
    '5',
    '50',
  ].map((s) => TextEditingController(text: s)).toList();
  @override
  void dispose() {
    for (final c in inputs) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final v = inputs.map((c) => double.tryParse(c.text)).toList();
    final valid =
        v.every((n) => n != null && n.isFinite) &&
        v[0]! > 0 &&
        v[0]! <= 1e15 &&
        v[1]! > 0 &&
        v[1]! <= 100 &&
        v[2]! >= 0 &&
        v[2]! <= 10000 &&
        v[3]! >= 0 &&
        v[3]! <= 10000 &&
        v[4]! >= 0 &&
        v[4]! <= 100 &&
        v[5]! >= 0 &&
        v[5]! <= 100;
    final r = valid
        ? TargetResult(
            portfolio: v[0]!,
            position: v[1]!,
            target: v[2]!,
            win: v[3]!,
            loss: v[4]!,
            success: v[5]!,
          )
        : null;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              '목표 계산기',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            for (int i = 0; i < inputs.length; i++)
              Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: TextField(
                  controller: inputs[i],
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: InputDecoration(
                    labelText: [
                      '계좌 자산 (원)',
                      '거래당 매수 비중 (%)',
                      '목표 계좌 수익률 (%)',
                      '평균 수익률 (%)',
                      '평균 손실률 (%)',
                      '승률 (%)',
                    ][i],
                  ),
                  onChanged: (_) => setState(() {}),
                ),
              ),
            if (r == null)
              const Text('금액과 비율의 범위를 확인하세요.')
            else
              Text(
                '거래당 매수금액 ${money(r.positionAmount)}\n수익 거래 ${money(r.winAmount)} · 손실 거래 ${money(r.lossAmount)}\n기대수익률 ${percent(r.expectancy)} · 기대금액 ${money(r.positionAmount * r.expectancy / 100)}\n목표금액 ${money(r.targetAmount)}\n손익비 ${ratio(r.rewardRisk)} · 조정 손익비 ${ratio(r.adjustedRatio)}\n이론상 필요 거래수 ${r.trades == null ? '계산 불가' : '${r.trades}회'}\nKelly 참고값 ${r.kelly == null ? '—' : '${r.kelly!.toStringAsFixed(2)}%'}',
              ),
            const SizedBox(height: 16),
            const Text(
              '동일한 승률·손익률과 고정된 초기 매수금액을 가정한 계산입니다. 복리, 비용, 수익의 변동은 반영하지 않습니다.',
              style: TextStyle(color: Colors.white60),
            ),
          ],
        ),
      ),
    );
  }
}
